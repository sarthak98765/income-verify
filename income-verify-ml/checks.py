"""Checks inside one document. Pure Python, no model: every number is recomputed from the extracted parts.
Each check is {"key", "status": pass|warn|fail, "message", "page", "fields": [paths it puts in doubt]}."""
import re
from typing import Dict, List
from config import *
from utils import PAN_RE, TAN_RE, close

LINE_PATTERNS = {
    "basic": r"\bbasic\b",
    "pf": r"provident|\bp\.?f\b|\bepf\b",
    "esi": r"\besic?\b|state insurance",
    "pt": r"prof(essional|\.)?\s*tax|\bp\.?\s?t\b",
    "tds": r"income\s*tax|\btds\b",
}

def check(key: str, ok: bool | None, message: str, page=None, fields: List[str] = (), warn_only: bool = False) -> Dict:
    status = "pass" if ok else ("warn" if warn_only or ok is None else "fail")
    return {"key": key, "status": status, "message": message, "page": page, "fields": list(fields) if not ok else []}

def line_amount(lines: List[Dict], name: str) -> float | None:
    """The amount of the first payslip line whose name matches LINE_PATTERNS[name]."""
    return next((l["amount"] for l in lines if re.search(LINE_PATTERNS[name], l["name"], re.I) and l["amount"] is not None), None)

def total(lines: List[Dict]) -> float:
    return round(sum(l["amount"] or 0 for l in lines), 2)

def rupees(x) -> str:
    return "—" if x is None else f"₹{x:,.2f}"

# ── Payslip ──────────────────────────────────────────────────────────────────

def sum_check(key: str, lines: str, parts: float, label: str, printed, page, fields: List[str]) -> Dict:
    """Lines vs the printed total. A total that couldn't be read is a warning (a person looks), never a failed sum:
    tampering needs a value that is present and wrong."""
    if printed is None:
        return check(key, None, f"Printed {label} could not be read, so the {lines.lower()} ({rupees(parts)}) can't be checked", page, fields)
    return check(key, close(parts, printed, AMOUNT_TOLERANCE), f"{lines} add up to {rupees(parts)}; printed {label} is {rupees(printed)}", page, fields)

def payslip_math(f: Dict) -> List[Dict]:
    page = f["page"]
    out = [
        sum_check("payslip_earnings_sum", "Earnings", total(f["earnings"]), "gross", f["gross"], page, ["gross", "earnings"]),
        sum_check("payslip_deductions_sum", "Deductions", total(f["deductions"]), "total", f["total_deductions"], page, ["total_deductions", "deductions"]),
    ]
    if f["gross"] is None or f["total_deductions"] is None:
        out.append(check("payslip_net_pay", None, "Gross or total deductions could not be read, so net pay can't be checked", page, ["net_pay"]))
    elif f["net_pay"] is None:
        out.append(check("payslip_net_pay", None, f"Net pay could not be read (gross − deductions = {rupees(round(f['gross'] - f['total_deductions'], 2))})", page, ["net_pay"]))
    else:
        net = round(f["gross"] - f["total_deductions"], 2)
        out.append(check("payslip_net_pay", close(net, f["net_pay"], AMOUNT_TOLERANCE), f"Gross − deductions = {rupees(net)}; printed net pay is {rupees(f['net_pay'])}", page, ["net_pay"]))
    return out

def expected_pt(state: str, gross: float):
    """(applies, amount): applies is False for a state with no professional tax; amount None when the state isn't known."""
    if state not in PT_SLABS:
        return True, None
    slabs = PT_SLABS[state]
    if slabs is None:
        return False, 0
    return True, next(tax for above, tax in slabs if gross > above)

def payslip_statutory(f: Dict) -> List[Dict]:
    page, gross = f["page"], f["gross"] or 0
    basic, pf = line_amount(f["earnings"], "basic"), line_amount(f["deductions"], "pf")
    esi, pt = line_amount(f["deductions"], "esi"), line_amount(f["deductions"], "pt")
    out = [check("pan_format", bool(PAN_RE.match(f["pan"])) if f["pan"] else None, f"PAN '{f['pan'] or 'missing'}' {'is valid' if PAN_RE.match(f['pan'] or '') else 'is not in the AAAAA9999A format'}", page, ["pan"], warn_only=not f["pan"])]
    if basic and pf:
        options = {round(basic * PF_RATE, 2), round(min(basic, PF_WAGE_CEILING) * PF_RATE, 2)}
        out.append(check("pf_rate", any(close(pf, o, 2) for o in options), f"PF {rupees(pf)} vs 12% of basic {' or '.join(rupees(o) for o in sorted(options))}", page, ["deductions"], warn_only=True))
    if gross:
        out.append(check("esi_applicability", not (esi and gross > ESI_GROSS_CEILING), f"ESI {'deducted' if esi else 'not deducted'} with gross {rupees(gross)} (ESI applies up to ₹{ESI_GROSS_CEILING:,})", page, ["deductions"], warn_only=True))
        applies, amount = expected_pt(f["work_state"], gross)
        if not applies:
            out.append(check("professional_tax", not pt, f"{f['work_state']} levies no professional tax, but the slip deducts {rupees(pt)}" if pt else f"No professional tax, as expected in {f['work_state']}", page, ["deductions"], warn_only=True))
        elif amount is not None:
            out.append(check("professional_tax", close(pt or 0, amount, 1), f"Professional tax {rupees(pt or 0)}; {f['work_state']} slab for this gross is {rupees(amount)}", page, ["deductions"], warn_only=True))
    if basic and gross:
        out.append(check("basic_share", basic / gross >= 0.3, f"Basic is {basic / gross:.0%} of gross" + ("" if basic / gross >= 0.3 else " — allowances look inflated"), page, ["earnings"], warn_only=True))
    return out

def payslip_checks(f: Dict) -> List[Dict]:
    return payslip_math(f) + payslip_statutory(f)

# ── Bank statement ───────────────────────────────────────────────────────────

def chain_breaks(opening, transactions: List[Dict]) -> List[Dict]:
    """Rows whose printed balance ≠ previous balance + credit − debit. The first row chains from the opening balance."""
    breaks, previous = [], opening
    for t in transactions:
        if previous is not None and t["balance"] is not None:
            expected = round(previous + t["amount"], 2)
            if not close(expected, t["balance"], AMOUNT_TOLERANCE):
                breaks.append({"row": t["row"], "page": t["page"], "expected": expected, "printed": t["balance"]})
        previous = t["balance"] if t["balance"] is not None else previous
    return breaks

def opening_of(f: Dict):
    """The printed opening balance, or the one implied by the first row when it isn't printed."""
    rows, opening = f["transactions"], f["account"]["opening_balance"]
    if opening is None and rows and rows[0]["balance"] is not None:
        opening = round(rows[0]["balance"] - rows[0]["amount"], 2)
    return opening

def statement_checks(f: Dict) -> List[Dict]:
    account, rows = f["account"], f["transactions"]
    opening = opening_of(f)
    breaks = chain_breaks(opening, rows)
    credits, debits = sum(t["credit"] or 0 for t in rows), sum(t["debit"] or 0 for t in rows)
    computed_close = round((opening or 0) + credits - debits, 2)
    dates = [t["date"] for t in rows if t["date"]]
    in_order = dates == sorted(dates)
    period = account["period_from"], account["period_to"]
    in_period = all(period[0] <= d <= period[1] for d in dates) if all(period) else None
    return [
        check("balance_chain", not breaks, f"Running balance reconciles on all {len(rows)} rows" if not breaks else f"Running balance breaks on {len(breaks)} of {len(rows)} rows (first: row {breaks[0]['row'] + 1}, page {breaks[0]['page']})", breaks[0]["page"] if breaks else None, [f"transactions.{b['row']}" for b in breaks]),
        check("closing_balance", close(computed_close, account["closing_balance"], AMOUNT_TOLERANCE), f"Opening + credits − debits = {rupees(computed_close)}; printed closing balance is {rupees(account['closing_balance'])}", None, ["account.closing_balance"]),
        check("dates_in_order", in_order, "Transaction dates are in order" if in_order else "Transaction dates are out of order", None, ["transactions"], warn_only=True),
        check("dates_in_period", in_period, "All transactions fall inside the statement period" if in_period else "Statement period missing or transactions outside it", None, ["account.period_from", "account.period_to"], warn_only=True),
        check("ifsc_format", account["ifsc_valid"] if account["ifsc"] else None, f"IFSC '{account['ifsc'] or 'missing'}'" + (" is valid" if account["ifsc_valid"] else " is not valid"), None, ["account.ifsc"], warn_only=True),
    ]

# ── Form 16 ──────────────────────────────────────────────────────────────────

def form16_checks(f: Dict) -> List[Dict]:
    page = f["page"]
    out = [
        check("pan_format", bool(PAN_RE.match(f["employee_pan"])), f"Employee PAN '{f['employee_pan'] or 'missing'}'", page, ["employee_pan"], warn_only=True),
        check("tan_format", bool(TAN_RE.match(f["employer_tan"])), f"Employer TAN '{f['employer_tan'] or 'missing'}'", page, ["employer_tan"], warn_only=True),
    ]
    if f["regime"] and f["standard_deduction"] is not None:
        expected = STANDARD_DEDUCTION[f["regime"]]
        out.append(check("standard_deduction", close(f["standard_deduction"], expected, 1), f"Standard deduction {rupees(f['standard_deduction'])}; {f['regime']} regime allows {rupees(expected)}", page, ["standard_deduction"], warn_only=True))
    parts = [f["gross_salary"], f["exemptions_section_10"], f["standard_deduction"], f["professional_tax"], f["chapter_via_deductions"]]
    if f["gross_salary"] is not None and f["taxable_income"] is not None:
        computed = round(parts[0] - sum(p or 0 for p in parts[1:]), 2)
        out.append(check("taxable_income", close(computed, f["taxable_income"], 10), f"Gross − exemptions − deductions = {rupees(computed)}; printed taxable income is {rupees(f['taxable_income'])}", page, ["taxable_income", "gross_salary"]))
    return out

CHECKS = {"payslip": payslip_checks, "bank_statement": statement_checks, "form16": form16_checks}
