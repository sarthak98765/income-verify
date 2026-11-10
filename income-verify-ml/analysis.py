"""Across documents: salary credits vs payslips, names, employer, annual income, metrics, and the verdict. Pure Python."""
import re
from datetime import date, timedelta
from statistics import median
from typing import Dict, List
from checks import check, rupees
from config import *
from tamper import authenticity, signal
from utils import close, month_of, names_match, next_month, to_date

EMI_AMOUNT_TOLERANCE = 0.02
LATEST_EDIT_SHARE = 0.05
SALARY_WINDOW = (20, 10)  # salary for month M is looked for from day 20 of M to day 10 of M+1

def of_type(docs: List[Dict], doc_type: str) -> List[Dict]:
    return [d for d in docs if d["doc_type"] == doc_type]

# ── Salary credits ───────────────────────────────────────────────────────────

def salary_window(month: str):
    start = date.fromisoformat(f"{month}-{SALARY_WINDOW[0]:02d}")
    end = date.fromisoformat(f"{next_month(month)}-{SALARY_WINDOW[1]:02d}")
    return start, end

def match_salary(payslip: Dict, transactions: List[Dict], used: set) -> Dict:
    """The credit paying this payslip: in the month's window, amount = net pay (±1%), salary-like rows preferred."""
    month, net = payslip["month"], payslip["net_pay"]
    if not month or net is None:
        return {"month": month, "net_pay": net, "credit": None}
    start, end = salary_window(month)
    candidates = [t for t in transactions if t["credit"] and t["date"] and start <= to_date(t["date"]) <= end and t["row"] not in used and close(t["credit"], net, max(AMOUNT_TOLERANCE, net * SALARY_MATCH_TOLERANCE))]
    candidates.sort(key=lambda t: (t.get("category") != "salary", abs(t["credit"] - net)))
    hit = candidates[0] if candidates else None
    if hit:
        used.add(hit["row"])
    return {"month": month, "net_pay": net, "credit": {"date": hit["date"], "amount": hit["credit"], "row": hit["row"], "page": hit["page"], "description": hit["description"]} if hit else None}

def salary_checks(payslips: List[Dict], transactions: List[Dict], covered) -> tuple:
    """(matches, checks). A payslip month outside the statement period is skipped, not failed."""
    used, matches, out = set(), [], []
    for p in sorted(payslips, key=lambda p: p["month"] or ""):
        if p["month"] and covered and not (covered[0][:7] <= p["month"] <= covered[1][:7]) and not (covered[0][:7] <= next_month(p["month"]) <= covered[1][:7]):
            continue
        m = match_salary(p, transactions, used)
        matches.append(m)
        if m["net_pay"] is None:
            # Nothing to look for: a blank net pay is a reading problem for a person, not a missing salary.
            out.append(check("salary_credit", None, f"{m['month'] or 'A payslip'}: net pay could not be read, so its salary credit can't be matched", None, ["net_pay"]))
        elif m["credit"]:
            out.append(check("salary_credit", True, f"{m['month']}: net pay {rupees(m['net_pay'])} credited on {m['credit']['date']}", m["credit"]["page"]))
        else:
            out.append(check("salary_credit", False, f"{m['month']}: no credit of {rupees(m['net_pay'])} found in the bank statement", None, ["net_pay"]))
    return matches, out

# ── Identity, employer, annual income ────────────────────────────────────────

def identity_checks(applicant: str, docs: List[Dict]) -> List[Dict]:
    names = [(d["doc_type"], d["fields"].get("employee_name") or (d["fields"].get("account") or {}).get("account_holder")) for d in docs]
    out = []
    for source, name in names:
        if name:
            ok = names_match(applicant, name, NAME_MATCH_MIN)
            out.append(check("name_match", ok, f"{source.replace('_', ' ')} name '{name}' {'matches' if ok else 'does not match'} applicant '{applicant}'", None, ["employee_name"]))
    return out

def employer_checks(declared: str, docs: List[Dict]) -> List[Dict]:
    names = [(d["doc_type"], d["fields"]["employer_name"]) for d in docs if d["doc_type"] in ("payslip", "form16") and d["fields"].get("employer_name")]
    reference = declared or (names[0][1] if names else "")
    out = []
    for source, name in names:
        ok = names_match(reference, name, NAME_MATCH_MIN)
        out.append(check("employer_match", ok, f"{source} employer '{name}' {'matches' if ok else 'does not match'} '{reference}'", None, ["employer_name"]))
    return out

def annual_income_check(form16s: List[Dict], payslips: List[Dict]) -> List[Dict]:
    gross = [p["gross"] for p in payslips if p["gross"]]
    out = []
    for f in form16s:
        if f["gross_salary"] and gross:
            expected = 12 * median(gross)
            ok = abs(f["gross_salary"] - expected) <= expected * ANNUAL_INCOME_TOLERANCE
            out.append(check("annual_income", ok, f"Form 16 gross {rupees(f['gross_salary'])} vs 12 × monthly gross {rupees(expected)}", f["page"], ["gross_salary"]))
    return out

def latest_month_signals(payslips: List[Dict]) -> List[Dict]:
    """Earlier months agree but the newest slip's gross or net jumps — a fraudster often edits only the latest slip."""
    dated = sorted([p for p in payslips if p["month"] and p["net_pay"]], key=lambda p: p["month"])
    if len(dated) < 3:
        return []
    earlier, latest = dated[:-1], dated[-1]
    base = median(p["net_pay"] for p in earlier)
    steady = all(abs(p["net_pay"] - base) <= base * 0.01 for p in earlier)
    if steady and abs(latest["net_pay"] - base) > base * LATEST_EDIT_SHARE:
        return [signal("latest_month_edit", f"{latest['month']} net pay {rupees(latest['net_pay'])} differs from the steady {rupees(base)} of earlier months", latest["page"])]
    return []

# ── Metrics ──────────────────────────────────────────────────────────────────

def daily_balances(transactions: List[Dict], opening, start: str, end: str) -> List[float]:
    """End-of-day balance for every day of the period, carrying the last known balance forward."""
    by_day = {}
    for t in transactions:
        if t["date"] and t["balance"] is not None:
            by_day[t["date"]] = t["balance"]
    day, last, out = to_date(start), opening, []
    while day <= to_date(end):
        last = by_day.get(day.isoformat(), last)
        if last is not None:
            out.append(last)
        day += timedelta(days=1)
    return out

def recurring_emis(transactions: List[Dict]) -> List[Dict]:
    """EMI debits grouped by amount (±2%); a group seen in 2+ months — or the only month covered — is an obligation."""
    groups: List[Dict] = []
    for t in (t for t in transactions if t.get("category") == "emi" and t["debit"]):
        g = next((g for g in groups if abs(g["amount"] - t["debit"]) <= g["amount"] * EMI_AMOUNT_TOLERANCE), None)
        if g is None:
            g = {"amount": t["debit"], "months": set(), "description": t["description"]}
            groups.append(g)
        g["months"].add(month_of(t["date"] or "0000-00"))
    covered = {month_of(t["date"]) for t in transactions if t["date"]}
    return [{"amount": g["amount"], "months": sorted(g["months"]), "description": g["description"]} for g in groups if len(g["months"]) >= 2 or len(covered) == 1]

def is_bounce_event(t: Dict) -> bool:
    """A returned payment counts once: the return itself, not the penalty charge booked next to it."""
    return t.get("category") == "bounce" and not re.search(r"\b(chg|chgs|charges?|fee)\b", t["description"], re.I)

def metrics(statement: Dict | None, matches: List[Dict]) -> Dict:
    credits = [m["credit"]["amount"] for m in matches if m["credit"]]
    income = round(median(credits), 2) if credits else None
    if not statement:
        return {"verified_monthly_income": income}
    rows, account = statement["transactions"], statement["account"]
    dates = [t["date"] for t in rows if t["date"]]
    start, end = account["period_from"] or (min(dates) if dates else None), account["period_to"] or (max(dates) if dates else None)
    balances = daily_balances(rows, account["opening_balance"], start, end) if start and end else []
    emis = recurring_emis(rows)
    emi_total = round(sum(e["amount"] for e in emis), 2)
    total_credit = sum(t["credit"] or 0 for t in rows)
    cash = sum(t["credit"] or 0 for t in rows if t.get("category") == "cash_deposit")
    return {
        "verified_monthly_income": income,
        "salary_months_matched": len(credits), "salary_months_checked": len(matches),
        "average_balance": round(sum(balances) / len(balances), 2) if balances else None,
        "minimum_balance": min(balances) if balances else None,
        "existing_emis": emis, "emi_total": emi_total,
        "bounces": [{"date": t["date"], "description": t["description"], "page": t["page"]} for t in rows if is_bounce_event(t)],
        "cash_deposit_share": round(cash / total_credit, 4) if total_credit else None,
        "foir": round(emi_total / income, 4) if income else None,
        "months_covered": len({d[:7] for d in dates}),
    }

# ── Verdict ──────────────────────────────────────────────────────────────────

def signals_from_checks(docs: List[Dict], salary: List[Dict]) -> List[Dict]:
    """Failed checks that read as tampering rather than misreading, turned into weighted signals."""
    found = []
    for d in docs:
        for c in d["checks"]:
            if c["status"] == "fail" and c["key"] in ("payslip_net_pay", "payslip_earnings_sum", "payslip_deductions_sum", "taxable_income"):
                found.append(signal("math_broken", f"{d['doc_type']}: {c['message']}", c["page"]))
            if c["status"] == "fail" and c["key"] == "balance_chain":
                found.append(signal("balance_chain_break", c["message"], c["page"]))
            if c["status"] == "warn" and c["key"] in ("pf_rate", "esi_applicability", "professional_tax"):
                found.append(signal("statutory_mismatch", f"{d['doc_type']}: {c['message']}", c["page"]))
    found += [signal("salary_not_credited", c["message"]) for c in salary if c["status"] == "fail"]
    return found

def verdict(docs: List[Dict], cross: List[Dict], signals: List[Dict]) -> Dict:
    score = authenticity(signals)
    hard_fails = [c for c in cross if c["status"] == "fail" and c["key"] in ("name_match", "salary_credit", "annual_income", "employer_match")]
    low = [f"{d['doc_type']}: {path}" for d in docs for path in d["confidence"]["low"]]
    unknown = [d["filename"] for d in docs if d["doc_type"] == "unknown"]
    missing = [t for t in ("payslip", "bank_statement") if not of_type(docs, t)]
    if score < AUTHENTICITY_FLAG_BELOW or hard_fails:
        status = "flagged"
    elif signals or low or unknown or missing or any(c["status"] != "pass" for c in cross):
        status = "needs_review"
    else:
        status = "verified"
    reasons = [s["message"] for s in signals] + [c["message"] for c in hard_fails] + [f"Low confidence: {x}" for x in low[:10]] + [f"Unrecognised document: {u}" for u in unknown] + [f"Missing a {m.replace('_', ' ')}" for m in missing]
    return {"status": status, "authenticity_score": score, "reasons": reasons}

def analyze(application: Dict, docs: List[Dict]) -> Dict:
    """Everything the application page shows, from processed documents (each {doc_type, filename, fields, checks, signals, confidence})."""
    payslips = [d["fields"] for d in of_type(docs, "payslip")]
    statements = of_type(docs, "bank_statement")
    statement = statements[0]["fields"] if statements else None
    rows = statement["transactions"] if statement else []
    covered = (statement["account"]["period_from"], statement["account"]["period_to"]) if statement and all((statement["account"]["period_from"], statement["account"]["period_to"])) else None
    matches, salary = salary_checks(payslips, rows, covered) if statement else ([], [])
    cross = salary + identity_checks(application["applicant_name"], docs) + employer_checks(application.get("declared_employer") or "", docs) + annual_income_check([d["fields"] for d in of_type(docs, "form16")], payslips)
    signals = [s for d in docs for s in d["signals"]] + signals_from_checks(docs, salary) + latest_month_signals(payslips)
    facts = metrics(statement, matches)
    declared = application.get("declared_monthly_income")
    if declared and facts.get("verified_monthly_income"):
        cross.append(check("declared_income", declared <= facts["verified_monthly_income"] * 1.1, f"Declared {rupees(declared)} vs verified {rupees(facts['verified_monthly_income'])} per month", warn_only=True))
    return {"metrics": facts, "salary_matches": matches, "cross_checks": cross, "signals": signals, **verdict(docs, cross, signals)}
