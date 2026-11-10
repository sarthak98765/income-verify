"""Compare one applicant's pipeline output with its truth.json, then roll everything up. Pure Python."""
from collections import Counter
from statistics import median
from typing import Dict, List
from utils import name_key

PAYSLIP_FIELDS = ["employee_name", "employer_name", "month", "gross", "total_deductions", "net_pay"]
BANK_FIELDS = ["account_holder", "opening_balance", "closing_balance"]
FORM16_FIELDS = ["employee_pan", "gross_salary", "standard_deduction", "taxable_income", "regime"]

NAME_FIELDS = {"employee_name", "employer_name", "account_holder"}

def same(expected, got, field: str = "") -> bool:
    """Amounts within 50 paise; names compared loosely (case, titles, punctuation); other text exactly, ignoring case and spacing."""
    if expected is None:
        return got is None
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return got is not None and abs(float(got) - float(expected)) < 0.5
    if field in NAME_FIELDS:
        return name_key(expected) == name_key(got)
    norm = lambda x: " ".join(str(x or "").split()).lower()
    return norm(expected) == norm(got)

def predicted_fields(doc: Dict) -> Dict:
    f = doc.get("fields") or {}
    if doc["doc_type"] == "bank_statement":
        return {**(f.get("account") or {}), "transactions": f.get("transactions") or []}
    return f

def field_hits(expected: Dict, got: Dict, names: List[str]) -> Dict[str, bool]:
    return {n: same(expected.get(n), got.get(n), n) for n in names}

def transaction_counts(expected: List[Dict], got: List[Dict]) -> Dict:
    key = lambda t: (t["date"], round(t["debit"] or 0, 2), round(t["credit"] or 0, 2), round(t["balance"] or 0, 2))
    want, have = Counter(key(t) for t in expected), Counter(key(t) for t in got)
    tp = sum((want & have).values())
    return {"tp": tp, "fp": sum(have.values()) - tp, "fn": sum(want.values()) - tp}

def fired_keys(output: Dict) -> set:
    """Every check (failed or warned) and signal key that the pipeline raised for this applicant."""
    r = output["result"]
    keys = {c["key"] for c in r["cross_checks"] if c["status"] != "pass"} | {s["key"] for s in r["signals"]}
    return keys | {c["key"] for d in output["documents"] for c in d["checks"] if c["status"] != "pass"}

def score_applicant(truth: Dict, output: Dict) -> Dict:
    by_file = {d["filename"]: d for d in output["documents"]}
    fields = {"payslip": [], "bank_statement": [], "form16": []}
    classified, tx, reconciled, documents = [], {"tp": 0, "fp": 0, "fn": 0}, None, []
    for t in truth["documents"]:
        doc = by_file.get(t["file"])
        classified.append(bool(doc) and doc["doc_type"] == t["doc_type"])
        if not doc or doc["doc_type"] != t["doc_type"]:
            continue
        got = predicted_fields(doc)
        names = {"payslip": PAYSLIP_FIELDS, "bank_statement": BANK_FIELDS, "form16": FORM16_FIELDS}[t["doc_type"]]
        hits = field_hits(t["fields"], got, names)
        fields[t["doc_type"]].append(hits)
        exact = all(hits.values())
        if t["doc_type"] == "bank_statement":
            tx = transaction_counts(t["fields"]["transactions"], got["transactions"])
            chain = next((c for c in doc["checks"] if c["key"] == "balance_chain"), None)
            reconciled = chain["status"] == "pass" if chain else False
            exact = exact and tx["fp"] == 0 and tx["fn"] == 0
        documents.append({"doc_type": t["doc_type"], "form": t.get("form"), "exact": exact,
                          "seconds": doc.get("eval_seconds"), "cost": (doc.get("eval_usage") or {}).get("cost_usd")})
    r, m, em = output["result"], output["result"]["metrics"], truth["expected_metrics"]
    keys = fired_keys(output)
    # a cross-check is right when it fires on its planted issue and passes on a clean applicant; knock-on
    # failures on a planted applicant (salary_mismatch also breaks annual_income) are not counted either way
    clean = truth["issue"] in (None, "bounces")
    cross = [(c["status"] != "pass") == (c["key"] in truth["expected_keys"]) for c in r["cross_checks"] if clean or c["key"] in truth["expected_keys"]]
    caught = r["status"] != "verified" and bool(set(truth["expected_keys"]) & keys) if truth["issue"] and truth["issue"] != "bounces" else None
    return {
        "id": truth["id"], "issue": truth["issue"], "expected_status": truth["expected_status"], "status": r["status"], "authenticity": r["authenticity_score"],
        "caught": caught, "fired": sorted(keys), "classified": classified, "fields": fields, "transactions": tx, "reconciled": reconciled,
        "documents": documents, "cross_checks": cross,
        "income_exact": same(em["verified_monthly_income"], m.get("verified_monthly_income")), "emi_exact": same(em["emi_total"], m.get("emi_total") or 0),
        "bounces_exact": em["bounces"] == len(m.get("bounces") or []), "seconds": output["seconds"], "cost": output["usage"]["cost_usd"],
    }

def share(items: List[bool]):
    items = [i for i in items if i is not None]
    return sum(items) / len(items) if items else None

def percentile(values: List[float], p: float) -> float:
    xs = sorted(values)
    return xs[min(len(xs) - 1, int(round((len(xs) - 1) * p)))] if xs else 0

def per_field(scored: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Accuracy of each field, per document type, to show which fields are hard."""
    out = {}
    for kind in ("payslip", "bank_statement", "form16"):
        rows = [hits for s in scored for hits in s["fields"][kind]]
        out[kind] = {name: share([h[name] for h in rows]) for name in (rows[0] if rows else {})}
    return out

def document_perf(scored: List[Dict]) -> Dict[str, Dict]:
    """Exact-match rate, latency p50/p95 and cost per document, per type and overall."""
    docs = [d for s in scored for d in s.get("documents", [])]
    groups = {"all": docs, **{k: [d for d in docs if d["doc_type"] == k] for k in ("payslip", "bank_statement", "form16")}}
    out = {}
    for name, ds in groups.items():
        secs = [d["seconds"] for d in ds if d["seconds"] is not None]
        costs = [d["cost"] for d in ds if d["cost"] is not None]
        out[name] = {"n": len(ds), "exact": share([d["exact"] for d in ds]), "seconds_p50": median(secs) if secs else None,
                     "seconds_p95": percentile(secs, 0.95) if secs else None, "cost": sum(costs) / len(costs) if costs else None}
    return out

def summarize(scored: List[Dict]) -> Dict:
    tp, fp, fn = (sum(s["transactions"][k] for s in scored) for k in ("tp", "fp", "fn"))
    precision, recall = (tp / (tp + fp) if tp + fp else 0), (tp / (tp + fn) if tp + fn else 0)
    clean = [s for s in scored if s["issue"] in (None, "bounces")]
    planted = [s for s in scored if s["issue"] not in (None, "bounces")]
    verified = [s for s in scored if s["status"] == "verified"]
    by_issue = {}
    for s in planted:
        row = by_issue.setdefault(s["issue"], {"caught": 0, "total": 0})
        row["total"] += 1
        row["caught"] += int(bool(s["caught"]))
    return {
        "applicants": len(scored), "documents": sum(len(s["classified"]) for s in scored),
        "classification_accuracy": share([c for s in scored for c in s["classified"]]),
        "field_accuracy": {k: share([v for s in scored for hits in s["fields"][k] for v in hits.values()]) for k in ("payslip", "bank_statement", "form16")},
        "transactions": {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0},
        "balance_reconciled": share([s["reconciled"] for s in scored if s["issue"] not in ("balance_edited",)]),
        "verdict_accuracy": share([s["status"] == s["expected_status"] for s in scored]),
        "issue_catch_rate": share([s["caught"] for s in planted]), "issues_caught": sum(1 for s in planted if s["caught"]), "issues_total": len(planted),
        "false_alarm_rate": share([s["status"] == "flagged" for s in clean]), "straight_through": share([s["status"] == "verified" for s in clean]),
        "auto_verified_precision": share([s["issue"] in (None, "bounces") for s in verified]),
        "income_exact": share([s["income_exact"] for s in scored]), "emi_exact": share([s["emi_exact"] for s in scored]), "bounces_exact": share([s["bounces_exact"] for s in scored]),
        "seconds_p50": round(median([s["seconds"] for s in scored]), 1) if scored else 0, "seconds_p95": percentile([s["seconds"] for s in scored], 0.95),
        "cost_per_applicant": sum(s["cost"] for s in scored) / len(scored) if scored else 0,
        "cross_check_accuracy": share([c for s in scored for c in s.get("cross_checks", [])]),
        "per_field": per_field(scored), "document_perf": document_perf(scored),
        "by_issue": by_issue, "confusion": Counter(f"{s['expected_status']}→{s['status']}" for s in scored),
    }
