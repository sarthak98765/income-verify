"""Synthetic applicants with ground truth.

  python -m data_gen.generate --split dev --count 10 --seed 1
  python -m data_gen.generate --split test --count 30 --seed 2

Writes data/<split>/<APPxxx>/{payslip_YYYY-MM.pdf|jpg, bank_statement.pdf, form16.pdf, truth.json} and data/<split>/manifest.json.
About 60% of applicants are clean; the rest carry one planted issue each (see fraud.ISSUES).
"""
import argparse
import copy
import json
import os
import random
from datetime import date
from typing import Dict, List
from faker import Faker
from data_gen import fraud, render, scan
from data_gen.bank_sim import month_days, simulate
from data_gen.profiles import STANDARD_DEDUCTION, annual_tax_new, make_applicant, totals

OUT = os.path.join(os.path.dirname(__file__), "..", "data")
STATEMENT_MONTHS = [(2026, m) for m in range(4, 10)]  # Apr–Sep 2026
PAYSLIP_MONTHS = STATEMENT_MONTHS[-3:]
CREATED = date(2026, 10, 3)
SCAN_SHARE = 0.3
CLEAN_SHARE = 0.6

def month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%B %Y")

def form16_values(app: Dict, monthly: Dict) -> Dict:
    gross = 12 * monthly["gross"]
    pt = 12 * dict(monthly["deductions"]).get("Professional Tax", 0)
    standard = STANDARD_DEDUCTION["new"]
    taxable = gross - standard - pt
    return {"assessment_year": "2026-27", "fy_start": 2025, "regime": "new", "gross_salary": gross, "exemptions_section_10": 0, "standard_deduction": standard,
            "professional_tax": pt, "chapter_via_deductions": 0, "taxable_income": taxable, "tax_deducted": round(annual_tax_new(taxable + pt))}

def truth_payslip(app: Dict, slip: Dict, ym: tuple) -> Dict:
    return {"employee_name": app["name"], "employer_name": app["employer"]["name"], "pan": app["pan"], "month": f"{ym[0]}-{ym[1]:02d}", "gross": slip["gross"], "total_deductions": slip["total_deductions"], "net_pay": slip["net_pay"]}

def truth_statement(holder: str, st: Dict) -> Dict:
    return {"account_holder": holder.upper(), "opening_balance": st["opening_balance"], "closing_balance": st["closing_balance"], "period_from": st["period_from"].isoformat(), "period_to": st["period_to"].isoformat(),
            "transactions": [{"date": t["date"].isoformat(), "debit": round(-t["amount"], 2) if t["amount"] < 0 else None, "credit": t["amount"] if t["amount"] > 0 else None, "balance": t["balance"]} for t in st["transactions"]]}

def emi_total(app: Dict, st: Dict) -> float:
    """EMIs that actually show up as debits in 2+ months (a debit the account couldn't afford was dropped by the simulator)."""
    total = 0.0
    for loan in app["loans"]:
        months = {t["date"].month for t in st["transactions"] if t["amount"] == -loan["emi"] and loan["lender"] in t["description"]}
        total += loan["emi"] if len(months) >= 2 else 0
    return total

def maybe_rough(rng: random.Random, pdf: bytes, kind: str, allowed: bool) -> tuple:
    """(bytes, extension, form): ~30% of documents become a scan (or, for payslips, sometimes a phone photo)."""
    if not allowed or rng.random() > SCAN_SHARE:
        return pdf, "pdf", "digital"
    if kind == "payslip" and rng.random() < 0.5:
        return scan.to_photo(pdf, rng), "jpg", "photo"
    return scan.to_scan(pdf, rng), "pdf", "scan"

def build(rng: random.Random, fake: Faker, index: int, issue: str | None, folder: str) -> Dict:
    app = make_applicant(rng, fake, index)
    if issue == "bounces" and not app["loans"]:
        app["loans"] = [{"lender": "SURYA FINANCE LTD", "emi": 8500, "loan_no": "4410029381"}]
    monthly = {**app["salary"], **totals(app["salary"])}
    bank_net = monthly["net_pay"]
    if issue == "statutory":
        fraud.wrong_pf(monthly)
        bank_net = monthly["net_pay"]
    statement = simulate(rng, fake, app, STATEMENT_MONTHS, bank_net, bounce_months=STATEMENT_MONTHS[2:4] if issue == "bounces" else ())
    slips = {ym: copy.deepcopy(monthly) for ym in PAYSLIP_MONTHS}
    if issue == "salary_mismatch":
        for slip in slips.values():
            fraud.inflate_payslip(slip, 0.25)
    if issue == "balance_edited":
        fraud.edit_balance(statement, rng)
    if issue == "fake_credit":
        fraud.insert_credit(statement, rng, fake.name())
    f16 = form16_values(app, monthly)
    if issue == "form16_mismatch":
        f16["gross_salary"] = round(f16["gross_salary"] * 1.35)
        f16["taxable_income"] = f16["gross_salary"] - f16["standard_deduction"] - f16["professional_tax"]
    holder = fake.name() if issue == "name_mismatch" else app["name"]

    files, docs = [], []
    os.makedirs(folder, exist_ok=True)
    def save(name: str, data: bytes, kind: str, form: str, fields: Dict):
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(data)
        files.append(name)
        docs.append({"file": name, "doc_type": kind, "form": form, "fields": fields})

    for k, ym in enumerate(PAYSLIP_MONTHS):
        slip = slips[ym]
        pdf = render.render_payslip(app, slip, index % 3, month_label(*ym), month_days(*ym), date(ym[0], ym[1], month_days(*ym)))
        latest = k == len(PAYSLIP_MONTHS) - 1
        if issue == "net_pay_edited" and latest:
            edited = slip["net_pay"] + round(slip["net_pay"] * 0.3 / 100) * 100
            pdf = fraud.edit_pdf_number(pdf, slip["net_pay"], edited)
            slip = {**slip, "net_pay": edited}
        data, ext, form = maybe_rough(rng, pdf, "payslip", allowed=not (issue == "net_pay_edited" and latest))
        save(f"payslip_{ym[0]}-{ym[1]:02d}.{ext}", data, "payslip", form, truth_payslip(app, slip, ym))
    st_app = {**app, "name": holder}
    pdf = render.render_statement(st_app, statement, index % 4, CREATED)
    if issue == "pdf_edited":
        pdf = fraud.mark_edited(pdf)
    data, ext, form = maybe_rough(rng, pdf, "bank_statement", allowed=issue != "pdf_edited")
    save(f"bank_statement.{ext}", data, "bank_statement", form, truth_statement(holder, statement))
    pdf = render.render_form16(app, f16, CREATED)
    data, ext, form = maybe_rough(rng, pdf, "form16", allowed=True)
    save(f"form16.{ext}", data, "form16", form, {k: f16[k] for k in ("gross_salary", "standard_deduction", "taxable_income", "regime")} | {"employee_pan": app["pan"]})

    expected_status, expected_keys = fraud.ISSUES[issue] if issue else ("verified", [])
    truth = {
        "id": app["id"], "issue": issue, "expected_status": expected_status, "expected_keys": expected_keys,
        "application": {"applicant_name": app["name"], "declared_employer": app["employer"]["name"], "declared_monthly_income": bank_net},
        "expected_metrics": {"verified_monthly_income": None if issue == "salary_mismatch" else bank_net, "emi_total": emi_total(app, statement), "bounces": 2 if issue == "bounces" else 0},
        "documents": docs,
    }
    with open(os.path.join(folder, "truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, default=str)
    return {"id": app["id"], "issue": issue, "files": files}

def plan_issues(rng: random.Random, count: int) -> List[str | None]:
    """~60% clean, the rest cycling through every issue so each appears at least once in a set of 25+."""
    issues = list(fraud.ISSUES)
    planted = [issues[i % len(issues)] for i in range(round(count * (1 - CLEAN_SHARE)))]
    out = planted + [None] * (count - len(planted))
    rng.shuffle(out)
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    rng, fake = random.Random(args.seed), Faker("en_IN")
    Faker.seed(args.seed)
    base = os.path.join(OUT, args.split)
    manifest = [build(rng, fake, args.seed * 1000 + i, issue, os.path.join(base, f"APP{args.seed * 1000 + i:03d}")) for i, issue in enumerate(plan_issues(rng, args.count))]
    with open(os.path.join(base, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"{len(manifest)} applicants → {os.path.abspath(base)}")
    for m in manifest:
        print(f"  {m['id']}  {m['issue'] or 'clean':16}  {', '.join(m['files'])}")

if __name__ == "__main__":
    main()
