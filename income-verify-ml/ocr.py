import asyncio
import base64
import hashlib
import json
import re
from typing import Dict, List
import httpx
import pymupdf
import storage
import usage
from config import *
from logger import custom_logger

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
IMAGE_TYPES = {"png", "jpg", "jpeg", "webp"}
# A short run repeated 50+ times: OCR got stuck in a loop and lost the rest of the page.
REPEAT_RE = re.compile(r"(.{1,40}?)(?:\s*\1){49,}", re.S)

class OcrError(RuntimeError):
    pass

def check(response: httpx.Response, what: str) -> Dict:
    if response.status_code in TRANSIENT_STATUS:
        raise httpx.HTTPStatusError(f"mistral {what} status {response.status_code}: {response.text[:300]}", request=response.request, response=response)
    if response.status_code >= 400:
        raise OcrError(f"mistral {what} status {response.status_code}: {response.text[:500]}")
    return response.json()

def as_pdf(data: bytes, filename: str) -> bytes:
    """Photos and scans arrive as images; wrap them in a one-page PDF so every document takes the same path."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in IMAGE_TYPES:
        return data
    with pymupdf.open(stream=data, filetype=ext) as img:
        return img.convert_to_pdf()

def page_count(pdf: bytes) -> int:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return doc.page_count

async def ocr_once(client: httpx.AsyncClient, pdf: bytes, filename: str) -> Dict:
    """Upload to Mistral's file store, OCR it, delete it — the PDF never needs a public URL."""
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    uploaded = check(await client.post(f"{MISTRAL_BASE_URL}/files", headers=headers, files={"file": (filename, pdf, "application/pdf")}, data={"purpose": "ocr"}), "upload")
    try:
        signed = check(await client.get(f"{MISTRAL_BASE_URL}/files/{uploaded['id']}/url", headers=headers, params={"expiry": 1}), "signed url")
        return check(await client.post(f"{MISTRAL_BASE_URL}/ocr", headers=headers, json={"model": OCR_MODEL, "document": {"type": "document_url", "document_url": signed["url"]}, "include_image_base64": False}), "ocr")
    finally:
        try:
            await client.delete(f"{MISTRAL_BASE_URL}/files/{uploaded['id']}", headers=headers)
        except Exception as e:
            custom_logger.warning(f"ocr | could not delete uploaded file: {e}")

async def ocr_page_image(client: httpx.AsyncClient, pdf: bytes, page_num: int) -> Dict:
    """One page rendered at a higher DPI and sent as an image — the fallback for a page that came back empty or looping."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        png = doc[page_num - 1].get_pixmap(dpi=OCR_RETRY_DPI).tobytes("png")
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    document = {"type": "image_url", "image_url": "data:image/png;base64," + base64.b64encode(png).decode()}
    return check(await client.post(f"{MISTRAL_BASE_URL}/ocr", headers=headers, json={"model": OCR_MODEL, "document": document}), f"ocr page {page_num}")

async def with_retry(call, *args) -> Dict:
    """5xx, timeouts and rate limits back off and retry; other 4xx fail at once."""
    async with httpx.AsyncClient(timeout=OCR_TIMEOUT) as client:
        for attempt in range(1, OCR_MAX_ATTEMPTS + 1):
            try:
                return await call(client, *args)
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                if attempt == OCR_MAX_ATTEMPTS:
                    raise OcrError(f"mistral ocr failed after {attempt} attempts: {e}") from e
                wait = OCR_BACKOFFS[min(attempt - 1, len(OCR_BACKOFFS) - 1)]
                custom_logger.warning(f"ocr | transient ({attempt}/{OCR_MAX_ATTEMPTS}): {e} — retry in {wait}s")
                await asyncio.sleep(wait)

def is_bad(markdown: str) -> bool:
    text = markdown or ""
    return len(text.strip()) < MIN_PAGE_CHARS or bool(REPEAT_RE.search(text))

async def reread_bad_pages(pdf: bytes, pages: List[Dict]) -> List[int]:
    """Re-read every empty or looping page as an image. Returns the page numbers that are still bad."""
    still = []
    for page in pages:
        if not is_bad(page["markdown"]):
            continue
        custom_logger.warning(f"ocr | page {page['page_number']} empty or looping — re-reading it as an image")
        data = await with_retry(ocr_page_image, pdf, page["page_number"])
        usage.add_ocr(1)
        page["markdown"] = REPEAT_RE.sub(r"\1", ((data.get("pages") or [{}])[0]).get("markdown") or "")
        if is_bad(page["markdown"]):
            still.append(page["page_number"])
    return still

async def read(data: bytes, filename: str) -> Dict:
    """Every page as markdown: {"pages": [{page_number, markdown}], "low_quality_pages": [...]}. Cached by content hash."""
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY is not set")
    pdf = as_pdf(data, filename)
    total = page_count(pdf)
    if total > MAX_PAGES:
        raise OcrError(f"{filename} has {total} pages; the limit is {MAX_PAGES}")
    cache_key = storage.key_for("ocr", f"{hashlib.sha256(pdf).hexdigest()}_{OCR_MODEL}_{OCR_CACHE_VERSION}.json")
    if await storage.exists(cache_key):
        custom_logger.info(f"ocr | cache hit {filename}")
        return json.loads(await storage.get(cache_key))
    raw = await with_retry(ocr_once, pdf, filename if filename.lower().endswith(".pdf") else filename + ".pdf")
    by_number = {p["index"] + 1: p.get("markdown") or "" for p in raw.get("pages") or []}
    usage.add_ocr((raw.get("usage_info") or {}).get("pages_processed") or len(by_number))
    pages = [{"page_number": n, "markdown": by_number.get(n, "")} for n in range(1, total + 1)]
    low = await reread_bad_pages(pdf, pages)
    result = {"pages": pages, "low_quality_pages": low}
    custom_logger.info(f"ocr | {filename}: {total} page(s), low quality: {low or 'none'}")
    if not low:
        await storage.put(cache_key, json.dumps(result).encode())
    return result
