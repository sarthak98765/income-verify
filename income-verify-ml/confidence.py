"""Per-field confidence. A field is `high` when its printed value is found in the OCR text, no check doubts it,
and its page read cleanly; otherwise `low`, with the reasons a reviewer needs."""
from typing import Dict, List
from utils import appears_in

# field path → key in the model's raw output (for the grounding check)
CRITICAL = {
    "payslip": {"employee_name": "employee_name", "employer_name": "employer_name", "month": "pay_month", "gross": "gross_earnings", "total_deductions": "total_deductions", "net_pay": "net_pay"},
    "bank_statement": {"account.account_holder": "account_holder", "account.opening_balance": "opening_balance", "account.closing_balance": "closing_balance"},
    "form16": {"employee_name": "employee_name", "employee_pan": "employee_pan", "gross_salary": "gross_salary", "taxable_income": "taxable_income"},
}

def doubted_by(path: str, checks: List[Dict]) -> List[str]:
    """Messages of the failed/warned checks that name this field (or its parent list)."""
    return [c["message"] for c in checks if c["status"] != "pass" and any(path == f or path.startswith(f + ".") for f in c["fields"])]

def raw_value(doc_type: str, raw: Dict, key: str):
    return (raw.get("account") or {}).get(key) if doc_type == "bank_statement" else raw.get(key)

def field_confidence(doc_type: str, raw: Dict, checks: List[Dict], text: str, low_pages: List[int], page, confirmed=()) -> Dict:
    """`confirmed`: paths a second, image-based read supplied and the arithmetic then agreed with — grounded even if
    the OCR text (which lost the layout) doesn't contain them."""
    out = {}
    for path, key in CRITICAL.get(doc_type, {}).items():
        reasons = doubted_by(path, checks)
        value = raw_value(doc_type, raw, key)
        if not str(value or "").strip():
            reasons.append("not found on the document")
        elif path in confirmed:
            pass
        elif not appears_in(value, text):
            reasons.append(f"'{value}' does not appear in the OCR text")
        if page in low_pages:
            reasons.append(f"page {page} read poorly")
        out[path] = {"level": "low" if reasons else "high", "reasons": reasons}
    return out

def transaction_confidence(transactions: List[Dict], checks: List[Dict], low_pages: List[int]) -> Dict:
    """Rows named by a failed check, or printed on a poorly read page, are low."""
    doubted = {f for c in checks if c["status"] == "fail" for f in c["fields"] if f.startswith("transactions.")}
    return {f"transactions.{t['row']}": {"level": "low", "reasons": ["balance does not reconcile" if f"transactions.{t['row']}" in doubted else f"page {t['page']} read poorly"]}
            for t in transactions if f"transactions.{t['row']}" in doubted or t["page"] in low_pages}

def score(doc: Dict, text: str, low_pages: List[int]) -> Dict:
    fields = doc["fields"]
    confirmed = (doc.get("reread") or {}).get("confirmed") or ()
    found = field_confidence(doc["doc_type"], doc["raw"], doc["checks"], text, low_pages, fields.get("page"), confirmed)
    if doc["doc_type"] == "bank_statement":
        found.update(transaction_confidence(fields["transactions"], doc["checks"], low_pages))
    return {"fields": found, "low": [p for p, v in found.items() if v["level"] == "low"]}
