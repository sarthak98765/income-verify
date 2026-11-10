import asyncio
import json
import time
from collections import namedtuple
import aio_pika
from aio_pika import DeliveryMode, IncomingMessage, Message
from aiormq.exceptions import ChannelInvalidStateError
import progress
import tracing
import usage
from config import *
from db import fetch_one, get_pool, update
from health import start_health_server
from logger import custom_logger
from tasks import pending_documents, run_analyze_application, run_process_document

Task = namedtuple("Task", "table run")
TASKS = {
    "process_document": Task("documents", run_process_document),
    "analyze_application": Task("applications", run_analyze_application),
}

async def publish(exchange, routing_key: str, body: dict, headers: dict = None) -> bool:
    try:
        await exchange.publish(Message(body=json.dumps(body).encode(), headers=headers or {}, delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json"), routing_key=routing_key)
        return True
    except Exception as e:
        custom_logger.error(f"worker | publish to {routing_key} failed: {e}")
        return False

async def record(pool, task: str, row: dict, tally, started: float, status: str, error: str = "") -> None:
    """One row of spend per run in usage_log. Never raises."""
    try:
        spent = tally.as_doc()
        await pool.execute("INSERT INTO usage_log (ref_kind, ref_id, task, status, calls, prompt_tokens, completion_tokens, ocr_pages, cost_usd, duration_s, by_model, error) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                           TASKS[task].table[:-1], row["id"], task, status, spent["calls"], spent["prompt_tokens"], spent["completion_tokens"], spent["ocr_pages"], spent["cost_usd"], round(time.monotonic() - started, 1), spent["by_model"], error[:500])
    except Exception as e:
        custom_logger.warning(f"worker | could not record usage for {task} {row.get('id')}: {e}")

async def after(pool, exchange, task: str, row: dict) -> None:
    """A finished document queues its application's analysis once no sibling is still pending."""
    if task == "process_document" and await pending_documents(pool, row["application_id"]) == 0:
        await update(pool, "applications", row["application_id"], {"status": "processing"})
        await publish(exchange, RABBITMQ_MAIN_QUEUE, {"task": "analyze_application", "id": str(row["application_id"])})

async def run_task(pool, exchange, task: str, row_id: str) -> None:
    """Load the row, mark it processing, run the task, save what it returns. Raises on failure (the retry ladder)."""
    t = TASKS[task]
    row = await fetch_one(pool, f"SELECT * FROM {t.table} WHERE id = $1", row_id)
    if not row:
        custom_logger.warning(f"worker | {task} {row_id} not found — dropping")
        return
    tally, started = usage.start(), time.monotonic()
    progress.start(pool, t.table, row["id"])
    tracing.start(task, row.get("application_id") or row["id"], {"row_id": str(row["id"]), "filename": row.get("filename", "")})
    await update(pool, t.table, row["id"], {"status": "processing", "error": ""})
    try:
        fields = await t.run(pool, row)
    except Exception as e:
        await record(pool, task, row, tally, started, "failed", str(e))
        raise
    done = {"status": "completed"} if task == "process_document" else {}
    await update(pool, t.table, row["id"], {**done, **(fields if task == "analyze_application" else {}), "usage": tally.as_doc(), "progress": {"stage": "done"}})
    await record(pool, task, row, tally, started, "completed")
    await after(pool, exchange, task, row)
    custom_logger.info(f"worker | completed {task} {row_id} cost=${tally.as_doc()['cost_usd']}")

async def handle_failure(pool, exchange, message: IncomingMessage, payload: dict, error: str) -> None:
    """main → retry (delayed by the retry queue's TTL) → after MAX_RETRIES, dead-letter with the row marked failed."""
    retries = int((message.headers or {}).get("x-retries", 0))
    task, row_id = payload.get("task"), payload.get("id")
    if retries >= MAX_RETRIES:
        custom_logger.error(f"worker | max retries exceeded | {task} {row_id}: {error}")
        if task in TASKS:
            try:
                await update(pool, TASKS[task].table, row_id, {"status": "failed", "error": error[:2000]})
                if task == "process_document":
                    row = await fetch_one(pool, "SELECT application_id FROM documents WHERE id = $1", row_id)
                    if row:
                        await after(pool, exchange, task, {"id": row_id, **row})
            except Exception as e:
                custom_logger.warning(f"worker | could not mark {task} {row_id} failed: {e}")
        await publish(exchange, RABBITMQ_DL_QUEUE, payload, {"x-retries": retries, "x-error": error[:500]})
    else:
        await publish(exchange, RABBITMQ_RETRY_QUEUE, payload, {"x-retries": retries + 1})

async def on_message(message: IncomingMessage, pool, exchange) -> None:
    """Consumer callback. MUST NOT throw — anything escaping can kill the consumer."""
    try:
        async with message.process(requeue=False, ignore_processed=True):
            try:
                payload = json.loads(message.body)
                task, row_id = payload["task"], payload["id"]
                if task not in TASKS:
                    raise ValueError(f"unknown task {task!r}")
            except Exception as e:
                custom_logger.error(f"worker | malformed payload (dropping): {e} | {message.body[:200]!r}")
                return
            custom_logger.info(f"worker | task={task} id={row_id}")
            try:
                await run_task(pool, exchange, task, row_id)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                custom_logger.exception(f"worker | failed {task} {row_id}: {e}")
                await handle_failure(pool, exchange, message, payload, str(e))
    except (ChannelInvalidStateError, RuntimeError, asyncio.CancelledError) as e:
        custom_logger.warning(f"worker | swallowed dead-channel error: {e}")
    except Exception as e:
        custom_logger.exception(f"worker | unexpected error (suppressed to keep consumer alive): {e}")

async def main():
    pool = await get_pool()
    connection = await aio_pika.connect_robust(RABBITMQ_URL, heartbeat=60, timeout=300)
    closed = asyncio.Event()
    connection.close_callbacks.add(lambda *_: closed.set())
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        exchange = await channel.get_exchange(RABBITMQ_EXCHANGE, ensure=False)
        queue = await channel.get_queue(RABBITMQ_MAIN_QUEUE, ensure=False)
        await queue.consume(lambda msg: on_message(msg, pool, exchange))
        custom_logger.info(f"worker | listening on {RABBITMQ_MAIN_QUEUE}")
        await closed.wait()
    await pool.close()

if __name__ == "__main__":
    start_health_server(HEALTH_PORT)
    delay = 5
    while True:
        try:
            asyncio.run(main())
            delay = 5
        except KeyboardInterrupt:
            custom_logger.info("worker | shutting down")
            break
        except Exception as e:
            custom_logger.exception(f"worker | crashed: {e} — restarting in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 60)
