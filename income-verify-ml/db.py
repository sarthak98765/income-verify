import json
import asyncpg
from config import DATABASE_URL

JSON_COLUMNS = {"low_quality_pages", "raw", "fields", "checks", "signals", "confidence", "reread", "progress", "usage", "metrics", "salary_matches", "cross_checks", "reasons", "by_model"}

async def init_connection(conn):
    for kind in ("json", "jsonb"):
        await conn.set_type_codec(kind, encoder=lambda v: json.dumps(v, default=str), decoder=json.loads, schema="pg_catalog")

async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4, init=init_connection)

async def fetch_one(pool, sql: str, *args) -> dict | None:
    row = await pool.fetchrow(sql, *args)
    return dict(row) if row else None

async def fetch_all(pool, sql: str, *args) -> list:
    return [dict(r) for r in await pool.fetch(sql, *args)]

async def update(pool, table: str, row_id, fields: dict) -> None:
    """UPDATE <table> SET <fields>, updated_at = now() WHERE id = row_id. Column names come from code, never from input."""
    if not fields:
        return
    names = list(fields)
    sets = ", ".join(f"{n} = ${i + 2}" for i, n in enumerate(names))
    await pool.execute(f"UPDATE {table} SET {sets}, updated_at = now() WHERE id = $1", row_id, *[fields[n] for n in names])
