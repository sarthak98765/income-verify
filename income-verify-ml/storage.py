import asyncio
import os
from config import STORAGE_DIR
from logger import custom_logger

class NoFile(Exception):
    pass

def key_for(*parts: str) -> str:
    """A storage key: key_for("ocr", "x.json") → "ocr/x.json". The backend writes uploads under "uploads/"."""
    return "/".join(parts)

def path_for(key: str) -> str:
    path = os.path.abspath(os.path.join(STORAGE_DIR, key))
    if not path.startswith(os.path.abspath(STORAGE_DIR)):
        raise ValueError(f"key escapes storage: {key}")
    return path

def write(key: str, data: bytes) -> None:
    path = path_for(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def read(key: str) -> bytes:
    try:
        with open(path_for(key), "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise NoFile(key)

async def put(key: str, data: bytes) -> str:
    await asyncio.to_thread(write, key, data)
    return key

async def get(key: str) -> bytes:
    return await asyncio.to_thread(read, key)

async def exists(key: str) -> bool:
    return await asyncio.to_thread(os.path.exists, path_for(key))

async def remove(key: str) -> int:
    try:
        await asyncio.to_thread(os.remove, path_for(key))
        custom_logger.info(f"storage | removed {key}")
        return 1
    except FileNotFoundError:
        return 0
