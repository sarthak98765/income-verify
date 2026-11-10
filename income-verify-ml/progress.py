import contextvars
import json
from datetime import datetime, timezone
from logger import custom_logger

CURRENT = contextvars.ContextVar("progress", default=None)

def start(pool, table: str, row_id: str):
    """Report progress for the task running in this context onto `<table>.progress` of row `row_id`. The pages poll it.
    With no pool (local runs) progress is only logged."""
    CURRENT.set((pool, table, row_id))

async def report(stage: str, **fields):
    """Record where the task is: {"stage", "stage_at", ...fields}. Never raises."""
    current = CURRENT.get()
    if not current:
        return
    pool, table, row_id = current
    value = {"stage": stage, "stage_at": datetime.now(timezone.utc).isoformat(), **fields}
    if pool is None:
        custom_logger.info(f"progress | {table} {row_id}: {stage} {fields or ''}")
        return
    try:
        await pool.execute(f"UPDATE {table} SET progress = $1::jsonb, updated_at = now() WHERE id = $2", json.dumps(value), row_id)
    except Exception as e:
        custom_logger.warning(f"progress | could not record {stage} for {table} {row_id}: {e}")
