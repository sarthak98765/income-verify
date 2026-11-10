"""Targeted second reads by a different (stronger) model.
Bank rows whose balance doesn't reconcile, and payslips whose totals came back blank (OCR lost a photo's table layout).
A misread gets fixed here; a document that really prints inconsistent numbers stays broken — and gets flagged."""
import base64
from typing import Dict, List
import pymupdf
from ai_client import get_ai_output
from checks import chain_breaks, opening_of, payslip_math
from config import MODEL_POLICY, OCR_RETRY_DPI
from extraction import normalize_payslip, normalize_row
from logger import custom_logger
from ocr import as_pdf
from prompts import PAYSLIP_PROMPT, PAYSLIP_IMAGE_NOTE, REREAD_ROWS_PROMPT
from utils import pages_text

NEIGHBOURS = 1

def rows_to_recheck(transactions: List[Dict], breaks: List[Dict]) -> Dict[int, List[int]]:
    """{page: [row indexes]} — each breaking row and its neighbours (an extra or missing row shifts the chain)."""
    out: Dict[int, List[int]] = {}
    for b in breaks:
        for i in range(max(0, b["row"] - NEIGHBOURS), min(len(transactions), b["row"] + NEIGHBOURS + 1)):
            page = transactions[i]["page"] or b["page"]
            out.setdefault(page, [])
            if i not in out[page]:
                out[page].append(i)
    return out

def describe(rows: List[Dict], doubted: set) -> str:
    return "\n".join(f"{'⚠ ' if t['row'] in doubted else ''}row {t['row']}: date={t['raw']['date']} | {t['description']} | debit={t['raw']['debit']} | credit={t['raw']['credit']} | balance={t['raw']['balance']}" for t in rows)

async def reread_page(page: Dict, rows: List[Dict], doubted: set) -> Dict[int, Dict]:
    prompt = f"**Page**\n{pages_text([page])}\n\n**Rows to re-check**\n{describe(rows, doubted)}"
    parsed = await get_ai_output(REREAD_ROWS_PROMPT, prompt, model=MODEL_POLICY["reread"], json_mode=True, name="reread_rows")
    fixed = {}
    for r in (parsed or {}).get("rows") or []:
        try:
            fixed[int(r["row"])] = r
        except (KeyError, TypeError, ValueError):
            continue
    return fixed

async def fix_breaks(fields: Dict, pages: List[Dict]) -> Dict:
    """Re-read the pages where the chain breaks and keep the corrected rows. Returns {"reread_rows", "fixed"}."""
    transactions = fields["transactions"]
    breaks = chain_breaks(opening_of(fields), transactions)
    if not breaks:
        return {"reread_rows": 0, "fixed": 0}
    by_page = {p["page_number"]: p for p in pages}
    doubted, changed, asked = {b["row"] for b in breaks}, 0, 0
    for page_num, indexes in rows_to_recheck(transactions, breaks).items():
        if page_num not in by_page:
            continue
        rows = [transactions[i] for i in indexes]
        asked += len(rows)
        for i, r in (await reread_page(by_page[page_num], rows, doubted)).items():
            if i in indexes:
                fresh = normalize_row({**transactions[i]["raw"], "description": transactions[i]["description"], "ref": transactions[i]["ref"], "page": transactions[i]["page"], **{k: r.get(k, "") for k in ("date", "debit", "credit", "balance")}}, i)
                if (fresh["debit"], fresh["credit"], fresh["balance"], fresh["date"]) != (transactions[i]["debit"], transactions[i]["credit"], transactions[i]["balance"], transactions[i]["date"]):
                    fresh["reread"] = True
                    transactions[i] = {**transactions[i], **fresh}
                    changed += 1
    left = len(chain_breaks(opening_of(fields), transactions))
    custom_logger.info(f"reread | {len(breaks)} break(s), re-read {asked} row(s), changed {changed}, {left} break(s) left")
    return {"reread_rows": asked, "fixed": changed, "breaks_before": len(breaks), "breaks_after": left}

# ── Payslip totals ───────────────────────────────────────────────────────────

PAYSLIP_TOTALS = ["gross", "total_deductions", "net_pay"]
MAX_IMAGE_PAGES = 2

def unsettled(fields: Dict) -> int:
    """How many of the payslip's sum checks don't pass."""
    return sum(c["status"] != "pass" for c in payslip_math(fields))

def page_images(data: bytes, filename: str) -> List[str]:
    """The first pages as PNG data URLs, rendered at the OCR retry DPI."""
    with pymupdf.open(stream=as_pdf(data, filename), filetype="pdf") as doc:
        pngs = [doc[i].get_pixmap(dpi=OCR_RETRY_DPI).tobytes("png") for i in range(min(MAX_IMAGE_PAGES, doc.page_count))]
    return ["data:image/png;base64," + base64.b64encode(png).decode() for png in pngs]

async def reread_payslip(doc: Dict, data: bytes, filename: str, pages: List[Dict]) -> Dict | None:
    """Read the page image again when a total came back blank. Only blanks trigger it: a total that is present but
    doesn't add up may be an edit, and is left for the checks. The new reading is kept only if every sum then passes,
    and its totals count as confirmed (they may not appear in the OCR text that lost the layout)."""
    fields = doc["fields"]
    blank = [k for k in PAYSLIP_TOTALS if fields.get(k) is None]
    if not blank:
        return None
    before = unsettled(fields)
    raw = await get_ai_output(PAYSLIP_PROMPT + PAYSLIP_IMAGE_NOTE, pages_text(pages), model=MODEL_POLICY["reread"], json_mode=True, images=page_images(data, filename), name="reread_payslip_image")
    raw = raw if isinstance(raw, dict) else {}
    fresh = normalize_payslip(raw)
    after = unsettled(fresh)
    keep = after == 0 and all(fresh.get(k) is not None for k in PAYSLIP_TOTALS)
    if keep:
        doc.update(raw=raw, fields=fresh)
    custom_logger.info(f"reread | payslip {filename}: blank {blank}, {before} sum check(s) open before, {after} after the image read, {'kept' if keep else 'discarded'}")
    return {"image_reread": True, "blank": blank, "fixed": int(keep), "confirmed": PAYSLIP_TOTALS if keep else []}
