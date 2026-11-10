from typing import Dict, List
from ai_client import get_ai_output, halving
from config import MODEL_POLICY, STATEMENT_BATCH_PAGES
from logger import custom_logger
from prompts import FORM16_PROMPT, PAYSLIP_PROMPT, STATEMENT_PROMPT
from utils import IFSC_RE, batch_pages, mask, pages_text, parse_amount, parse_date, parse_month

ACCOUNT_KEYS = ["bank_name", "branch", "account_holder", "account_number", "ifsc", "period_from", "period_to", "opening_balance", "closing_balance"]

# ── Payslip ──────────────────────────────────────────────────────────────────

def normalize_payslip(raw: Dict) -> Dict:
    """Model output (strings as printed) → numbers and ISO months. `raw` is kept beside it for grounding checks."""
    text = lambda k: str(raw.get(k) or "").strip()
    lines = lambda key: [{"name": str(r.get("name") or "").strip(), "amount": parse_amount(r.get("amount")), "raw": r.get("amount") or ""} for r in raw.get(key) or [] if isinstance(r, dict) and str(r.get("name") or "").strip()]
    return {
        "employer_name": text("employer_name"), "employer_cin": text("employer_cin"), "employee_name": text("employee_name"),
        "employee_id": text("employee_id"), "pan": text("pan").upper(), "work_state": text("work_state"),
        "month": parse_month(raw.get("pay_month")), "earnings": lines("earnings"), "deductions": lines("deductions"),
        "gross": parse_amount(raw.get("gross_earnings")), "total_deductions": parse_amount(raw.get("total_deductions")),
        "net_pay": parse_amount(raw.get("net_pay")), "bank_account": mask(text("bank_account")[-4:]), "page": raw.get("page") or 1,
    }

async def extract_payslip(pages: List[Dict]) -> Dict:
    raw = await get_ai_output(PAYSLIP_PROMPT, pages_text(pages), model=MODEL_POLICY["extract"], json_mode=True, name="extract_payslip")
    raw = raw if isinstance(raw, dict) else {}
    return {"raw": raw, "fields": normalize_payslip(raw)}

# ── Bank statement ───────────────────────────────────────────────────────────

def normalize_row(r: Dict, index: int) -> Dict:
    debit, credit = parse_amount(r.get("debit")), parse_amount(r.get("credit"))
    debit, credit = abs(debit) if debit else None, abs(credit) if credit else None
    return {"row": index, "date": parse_date(r.get("date")), "description": " ".join(str(r.get("description", "")).split()), "ref": str(r.get("ref", "")).strip(),
            "debit": debit, "credit": credit, "amount": round((credit or 0) - (debit or 0), 2), "balance": parse_amount(r.get("balance")), "page": r.get("page"), "raw": {k: r.get(k, "") for k in ("date", "debit", "credit", "balance")}}

def row_key(r: Dict) -> tuple:
    return (r.get("date"), r.get("debit"), r.get("credit"), r.get("balance"))

def drop_duplicates(rows: List[Dict]) -> List[Dict]:
    """A row read twice at a batch boundary: same date, amounts and balance, back to back."""
    out = []
    for r in rows:
        if out and row_key(out[-1]) == row_key(r):
            continue
        out.append(r)
    return out

def merge_account(parts: List[Dict]) -> Dict:
    """Account details from every batch: the first non-empty value wins, except the closing balance, which is printed last."""
    account = {k: "" for k in ACCOUNT_KEYS}
    for part in parts:
        for k in ACCOUNT_KEYS:
            value = str(part.get(k, "") or "").strip()
            if value and (not account[k] or k == "closing_balance"):
                account[k] = value
    return account

def normalize_account(raw: Dict) -> Dict:
    return {"bank_name": raw["bank_name"], "branch": raw["branch"], "account_holder": raw["account_holder"], "account_number": mask(raw["account_number"][-4:]),
            "ifsc": raw["ifsc"].upper().replace(" ", ""), "ifsc_valid": bool(IFSC_RE.match(raw["ifsc"].upper().replace(" ", ""))),
            "period_from": parse_date(raw["period_from"]), "period_to": parse_date(raw["period_to"]),
            "opening_balance": parse_amount(raw["opening_balance"]), "closing_balance": parse_amount(raw["closing_balance"])}

async def extract_statement(pages: List[Dict]) -> Dict:
    """Pages in batches, each with the next page as context only, so a row split by a page break is read once and whole."""
    batches = batch_pages(pages, STATEMENT_BATCH_PAGES)
    accounts, rows = [], []
    for i, batch in enumerate(batches):
        context = batches[i + 1][:1] if i + 1 < len(batches) else []
        async def call(chunk, start, context=context, batch=batch):
            following = batch[start + len(chunk):start + len(chunk) + 1] or context
            parsed = await get_ai_output(STATEMENT_PROMPT, pages_text(chunk, following), model=MODEL_POLICY["extract"], json_mode=True, name="extract_statement")
            parsed = parsed if isinstance(parsed, dict) else {}
            accounts.append(parsed.get("account") or {})
            return [t for t in parsed.get("transactions") or [] if isinstance(t, dict)]
        rows += await halving(batch, call)
        custom_logger.info(f"extraction | statement batch {i + 1}/{len(batches)}: {len(rows)} rows so far")
    account = merge_account(accounts)
    transactions = drop_duplicates([normalize_row(r, i) for i, r in enumerate(rows)])
    for i, t in enumerate(transactions):
        t["row"] = i
    return {"raw": {"account": account, "transactions": rows}, "fields": {"account": normalize_account(account), "transactions": transactions}}

# ── Form 16 ──────────────────────────────────────────────────────────────────

FORM16_AMOUNTS = ["gross_salary", "exemptions_section_10", "standard_deduction", "professional_tax", "chapter_via_deductions", "taxable_income", "tax_deducted"]

def normalize_form16(raw: Dict) -> Dict:
    text = lambda k: str(raw.get(k, "") or "").strip()
    regime = text("regime").lower()
    return {"employer_name": text("employer_name"), "employer_tan": text("employer_tan").upper(), "employee_name": text("employee_name"),
            "employee_pan": text("employee_pan").upper(), "assessment_year": text("assessment_year"), "regime": regime if regime in ("new", "old") else "",
            **{k: parse_amount(raw.get(k)) for k in FORM16_AMOUNTS}, "page": raw.get("page") or 1}

async def extract_form16(pages: List[Dict]) -> Dict:
    raw = await get_ai_output(FORM16_PROMPT, pages_text(pages), model=MODEL_POLICY["extract"], json_mode=True, name="extract_form16")
    raw = raw if isinstance(raw, dict) else {}
    return {"raw": raw, "fields": normalize_form16(raw)}

EXTRACTORS = {"payslip": extract_payslip, "bank_statement": extract_statement, "form16": extract_form16}
