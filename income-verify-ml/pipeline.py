"""The two tasks, free of the queue and the database so they run the same from the worker, run_local.py and the evals."""
from typing import Dict, List
import ocr
import progress
from analysis import analyze
from categorize import categorize
from checks import CHECKS
from classify import classify
from confidence import score
from extraction import EXTRACTORS
from logger import custom_logger
from reread import fix_breaks, reread_payslip
from summary import write_summary
from tamper import font_signals, metadata_signals, transaction_signals

def empty_doc(filename: str) -> Dict:
    return {"filename": filename, "doc_type": "unknown", "classified_by": "", "pages": 0, "low_quality_pages": [], "raw": {}, "fields": {}, "checks": [], "signals": [], "confidence": {"fields": {}, "low": []}, "reread": None}

def file_signals(data: bytes, filename: str) -> List[Dict]:
    """Metadata and font signals only mean something for a real PDF — an uploaded photo has neither."""
    if not filename.lower().endswith(".pdf"):
        return []
    try:
        return metadata_signals(data) + font_signals(data)
    except Exception as e:
        custom_logger.warning(f"pipeline | tamper scan failed for {filename}: {e}")
        return []

async def process_document(data: bytes, filename: str, use_reread: bool = True) -> Dict:
    """OCR → classify → extract → (bank: categorise, re-read breaks) → checks → signals → confidence."""
    doc = empty_doc(filename)
    await progress.report("reading")
    read = await ocr.read(data, filename)
    pages = read["pages"]
    doc.update(pages=len(pages), low_quality_pages=read["low_quality_pages"])
    await progress.report("classifying")
    kind = await classify(pages)
    doc.update(doc_type=kind["doc_type"], classified_by=kind["method"])
    if doc["doc_type"] == "unknown":
        return doc
    await progress.report("extracting", doc_type=doc["doc_type"])
    doc.update(await EXTRACTORS[doc["doc_type"]](pages))
    fields = doc["fields"]
    if doc["doc_type"] == "bank_statement":
        await progress.report("categorising", rows=len(fields["transactions"]))
        await categorize(fields["transactions"])
        if use_reread:
            await progress.report("rechecking")
            doc["reread"] = await fix_breaks(fields, pages)
    if doc["doc_type"] == "payslip" and use_reread and any(fields.get(k) is None for k in ("gross", "total_deductions", "net_pay")):
        await progress.report("rechecking")
        doc["reread"] = await reread_payslip(doc, data, filename, pages)
        fields = doc["fields"]
    await progress.report("checking")
    doc["checks"] = CHECKS[doc["doc_type"]](fields)
    doc["signals"] = file_signals(data, filename)
    if doc["doc_type"] == "bank_statement":
        doc["signals"] += transaction_signals(fields["transactions"], fields["account"]["period_to"])
    doc["confidence"] = score(doc, "\n".join(p["markdown"] for p in pages), doc["low_quality_pages"])
    custom_logger.info(f"pipeline | {filename}: {doc['doc_type']}, {sum(c['status'] != 'pass' for c in doc['checks'])} check(s) not passed, {len(doc['signals'])} signal(s), {len(doc['confidence']['low'])} low field(s)")
    return doc

async def analyze_application(application: Dict, docs: List[Dict], use_summary: bool = True) -> Dict:
    """Cross-checks, metrics, verdict and the underwriter note for one applicant."""
    await progress.report("analysing")
    result = analyze(application, docs)
    if use_summary:
        await progress.report("summarising")
        result.update(await write_summary(application, result))
    custom_logger.info(f"pipeline | {application['applicant_name']}: {result['status']} (authenticity {result['authenticity_score']})")
    return result
