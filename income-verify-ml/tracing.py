"""Langfuse tracing over its public ingestion API: one trace per task, one generation per model call (name, model,
tokens, cost, latency, error). Optional: with no keys it does nothing. Sending runs in the background and never
raises, so tracing can't slow down or break a task."""
import asyncio
import contextvars
import uuid
from datetime import datetime, timezone
from typing import Dict, List
import httpx
from config import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, TRACE_IO_CHARS
from logger import custom_logger

CURRENT = contextvars.ContextVar("trace", default=None)
PENDING: set = set()

def enabled() -> bool:
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def event(kind: str, body: Dict) -> Dict:
    return {"id": str(uuid.uuid4()), "timestamp": now(), "type": kind, "body": body}

def start(name: str, ref_id: str = "", metadata: Dict | None = None) -> None:
    """Open a trace for the task running in this context; its model calls attach to it."""
    if not enabled():
        return
    trace = {"id": str(uuid.uuid4()), "opened": False, "name": name, "ref_id": str(ref_id), "metadata": metadata or {}}
    CURRENT.set(trace)

def clip(value) -> str:
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= TRACE_IO_CHARS else text[:TRACE_IO_CHARS] + f"… [{len(text) - TRACE_IO_CHARS} more chars]"

def generation_events(trace: Dict, name: str, model: str, prompt: str, output, usage, cost: float, started: str, ended: str, error: str = "") -> List[Dict]:
    """The events for one model call: the trace itself the first time, then the generation."""
    events = []
    if not trace["opened"]:
        trace["opened"] = True
        events.append(event("trace-create", {"id": trace["id"], "name": trace["name"], "sessionId": trace["ref_id"] or None, "metadata": trace["metadata"], "tags": ["income-verify"]}))
    events.append(event("generation-create", {
        "id": str(uuid.uuid4()), "traceId": trace["id"], "name": name, "model": model, "startTime": started, "endTime": ended,
        "input": clip(prompt), "output": clip(output) if output is not None else None,
        "usage": {"input": getattr(usage, "prompt_tokens", 0) or 0, "output": getattr(usage, "completion_tokens", 0) or 0, "unit": "TOKENS", "totalCost": round(cost, 6)},
        "level": "ERROR" if error else "DEFAULT", "statusMessage": error[:500] or None,
    }))
    return events

async def send(events: List[Dict]) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{LANGFUSE_HOST}/api/public/ingestion", json={"batch": events}, auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY))
        if r.status_code >= 300:
            custom_logger.warning(f"tracing | langfuse status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        custom_logger.warning(f"tracing | could not send to langfuse: {e}")

def generation(name: str, model: str, prompt: str, output, usage, cost: float, started: str, error: str = "") -> None:
    """Record one model call on the current trace, in the background."""
    trace = CURRENT.get()
    if not enabled() or trace is None:
        return
    task = asyncio.get_running_loop().create_task(send(generation_events(trace, name, model, prompt, output, usage, cost, started, now(), error)))
    PENDING.add(task)
    task.add_done_callback(PENDING.discard)

async def flush() -> None:
    """Wait for the sends still in flight (end of a CLI run or an eval)."""
    if PENDING:
        await asyncio.gather(*PENDING, return_exceptions=True)
