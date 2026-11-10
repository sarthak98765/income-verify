"""What each queue task does with the database: load the row, run the pipeline, save what it returns."""
from typing import Dict, List
import storage
from checks import CHECKS
from confidence import transaction_confidence
from db import fetch_all, fetch_one, update
from logger import custom_logger
from pipeline import analyze_application, process_document

DOC_RESULT_COLUMNS = ["doc_type", "classified_by", "pages", "low_quality_pages", "raw", "fields", "checks", "signals", "confidence", "reread"]

async def run_process_document(pool, document: Dict) -> Dict:
    data = await storage.get(document["storage_key"])
    doc = await process_document(data, document["filename"])
    await update(pool, "documents", document["id"], {k: doc[k] for k in DOC_RESULT_COLUMNS})
    return doc

async def pending_documents(pool, application_id) -> int:
    row = await fetch_one(pool, "SELECT count(*) AS n FROM documents WHERE application_id = $1 AND status IN ('queued', 'processing')", application_id)
    return row["n"]

def apply_edits(doc: Dict, edited: List[str]) -> Dict:
    """Re-run the checks on the (possibly corrected) fields; a field a reviewer typed in is trusted."""
    if doc["doc_type"] not in CHECKS:
        return doc
    doc["checks"] = CHECKS[doc["doc_type"]](doc["fields"])
    conf = doc["confidence"] or {"fields": {}, "low": []}
    if doc["doc_type"] == "bank_statement":
        # row doubts come only from the checks, so recompute them: fixing one balance clears its neighbour too
        rows = transaction_confidence(doc["fields"]["transactions"], doc["checks"], doc.get("low_quality_pages") or [])
        conf["fields"] = {**{p: v for p, v in conf["fields"].items() if not p.startswith("transactions.")}, **rows}
    for path in edited:
        # an edit to transactions.12.debit also clears the row-level entry transactions.12
        covered = [p for p in conf["fields"] if path == p or path.startswith(p + ".")] or [path]
        for p in covered:
            conf["fields"][p] = {"level": "high", "reasons": ["corrected by reviewer"]}
    conf["low"] = [p for p, v in conf["fields"].items() if v["level"] == "low"]
    doc["confidence"] = conf
    return doc

async def run_analyze_application(pool, application: Dict) -> Dict:
    docs = await fetch_all(pool, "SELECT * FROM documents WHERE application_id = $1 AND status = 'completed' ORDER BY created_at", application["id"])
    edits = await fetch_all(pool, "SELECT DISTINCT document_id, field_path FROM field_edits WHERE document_id = ANY($1::uuid[])", [d["id"] for d in docs])
    for d in docs:
        apply_edits(d, [e["field_path"] for e in edits if e["document_id"] == d["id"]])
        await update(pool, "documents", d["id"], {"checks": d["checks"], "confidence": d["confidence"]})
    app = {"applicant_name": application["applicant_name"], "declared_employer": application["declared_employer"], "declared_monthly_income": float(application["declared_monthly_income"]) if application["declared_monthly_income"] is not None else None}
    result = await analyze_application(app, docs)
    m = result["metrics"]
    fields = {"status": result["status"], "authenticity_score": result["authenticity_score"], "verified_monthly_income": m.get("verified_monthly_income"), "foir": m.get("foir"),
              "metrics": m, "salary_matches": result["salary_matches"], "cross_checks": result["cross_checks"], "signals": result["signals"], "reasons": result["reasons"],
              "summary": result.get("summary", ""), "summary_by": result.get("summary_by", "")}
    await pool.execute("UPDATE applications SET analyzed_at = now() WHERE id = $1", application["id"])
    custom_logger.info(f"tasks | application {application['id']}: {result['status']}")
    return fields
