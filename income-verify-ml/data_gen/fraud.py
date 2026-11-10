"""Planted issues, done the way a fraudster would: edit the numbers, or edit the finished PDF.
Each issue lists what should catch it, so the evals can score the catch rate per issue."""
import random
from datetime import timedelta
from typing import Dict
import pymupdf
from data_gen.bank_sim import rebalance
from data_gen.render import inr

ISSUES = {
    # issue: (expected verdict, keys of the checks or signals that should fire)
    "net_pay_edited": ("flagged", ["odd_font", "math_broken", "salary_credit"]),
    "salary_mismatch": ("flagged", ["salary_credit"]),
    "balance_edited": ("flagged", ["balance_chain"]),
    "fake_credit": ("needs_review", ["window_dressing"]),
    "name_mismatch": ("flagged", ["name_match"]),
    "form16_mismatch": ("flagged", ["annual_income"]),
    "statutory": ("needs_review", ["pf_rate"]),
    "pdf_edited": ("needs_review", ["pdf_edited"]),
    "bounces": ("verified", []),  # a true finding about the applicant, not fraud: must NOT be flagged
}

# ── Before rendering: change the data ────────────────────────────────────────

def inflate_payslip(slip: Dict, share: float) -> None:
    """Raise the special allowance so gross and net go up consistently — the slip still adds up, but the bank won't agree."""
    bump = round(slip["gross"] * share / 100) * 100
    slip["earnings"] = [(n, a + bump if n == "Special Allowance" else a) for n, a in slip["earnings"]]
    slip["gross"] += bump
    slip["net_pay"] += bump

def edit_balance(statement: Dict, rng: random.Random) -> int:
    """Raise one printed balance in the middle of the statement without touching the rows around it."""
    rows = statement["transactions"]
    i = rng.randint(len(rows) // 3, 2 * len(rows) // 3)
    rows[i]["balance"] = round(rows[i]["balance"] + rng.choice([10000, 25000, 50000]), 2)
    return i

def insert_credit(statement: Dict, rng: random.Random, who: str) -> Dict:
    """A big round credit a few days before the statement ends, with every later balance fixed up to match."""
    when = statement["period_to"] - timedelta(days=rng.randint(1, 4))
    amount = float(rng.choice([150000, 200000, 250000, 300000]))
    row = {"date": when, "description": f"IMPS-{rng.randint(10**11, 10**12 - 1)}-{who.upper()}", "ref": str(rng.randint(10**11, 10**12 - 1)), "amount": amount, "balance": 0.0}
    rows = statement["transactions"]
    i = next((k for k, r in enumerate(rows) if r["date"] > when), len(rows))
    rows.insert(i, row)
    rebalance(statement, i)
    return row

def wrong_pf(slip: Dict) -> None:
    """PF far below 12% of basic, with the totals kept consistent."""
    basic = dict(slip["earnings"])["Basic Salary"]
    old = dict(slip["deductions"])["Provident Fund"]
    new = round(basic * 0.04)
    slip["deductions"] = [(n, new if n == "Provident Fund" else a) for n, a in slip["deductions"]]
    slip["total_deductions"] += new - old
    slip["net_pay"] -= new - old

# ── After rendering: edit the PDF ────────────────────────────────────────────

def edit_pdf_number(pdf: bytes, old: float, new: float) -> bytes:
    """White out a printed amount and type a new one over it in another font — what a quick PDF edit leaves behind."""
    target = inr(old)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            hits = page.search_for(target)
            for rect in hits:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()
            for rect in hits:
                page.insert_text((rect.x0, rect.y1 - 1.5), inr(new), fontname="cour", fontsize=rect.height * 0.75)
        doc.set_metadata({**doc.metadata, "producer": "iLovePDF", "modDate": doc.metadata.get("creationDate", "")[:2] + "20261020120000+05'30'"})
        return doc.tobytes(garbage=3, deflate=True)

def mark_edited(pdf: bytes) -> bytes:
    """Only the file history changes: re-saved by an online editor, modified after it was created."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        doc.set_metadata({**doc.metadata, "producer": "iLovePDF", "creator": "iLovePDF", "modDate": "D:20261021094500+05'30'"})
        return doc.tobytes(garbage=3, deflate=True)
