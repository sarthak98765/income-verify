"""Checks inside one document, the cross-document analysis, tamper signals and the summary guard. Pure Python."""
import unittest
from analysis import analyze, latest_month_signals, match_salary, recurring_emis
from checks import chain_breaks, expected_pt, payslip_checks, statement_checks
from summary import is_grounded
from tamper import authenticity, circular_signals, window_dressing_signals


def payslip(net=36080.0, pf=1920.0, state="Uttar Pradesh", month="2026-08", gross=38000.0):
    earnings = [{"name": "Basic Salary", "amount": 16000.0}, {"name": "Special Allowance", "amount": gross - 16000.0}]
    deductions = [{"name": "Provident Fund", "amount": pf}]
    return {"employer_name": "Natarajan Pharma Pvt Ltd", "employee_name": "Chaman Dara", "pan": "NGQPD5133P", "work_state": state, "month": month,
            "earnings": earnings, "deductions": deductions, "gross": gross, "total_deductions": pf, "net_pay": net, "page": 1}


def row(i, date, amount, balance, description="UPI/SWIGGY", category="upi"):
    return {"row": i, "date": date, "description": description, "amount": amount, "debit": -amount if amount < 0 else None,
            "credit": amount if amount > 0 else None, "balance": balance, "page": 1, "category": category}


def statement(rows, opening=1000.0, closing=None):
    return {"account": {"opening_balance": opening, "closing_balance": rows[-1]["balance"] if closing is None else closing, "period_from": "2026-07-01",
                        "period_to": "2026-09-30", "ifsc": "NRMX0810433", "ifsc_valid": True, "account_holder": "CHAMAN DARA"}, "transactions": rows}


class PayslipChecks(unittest.TestCase):
    def status(self, checks, key):
        return next(c["status"] for c in checks if c["key"] == key)

    def test_clean_slip_passes(self):
        checks = payslip_checks(payslip())
        self.assertTrue(all(c["status"] == "pass" for c in checks), [c for c in checks if c["status"] != "pass"])

    def test_edited_net_pay_fails_the_math(self):
        self.assertEqual(self.status(payslip_checks(payslip(net=46080.0)), "payslip_net_pay"), "fail")

    def test_unreadable_totals_warn_instead_of_failing(self):
        slip = {**payslip(), "gross": None, "net_pay": None}
        checks = payslip_checks(slip)
        self.assertEqual([self.status(checks, k) for k in ("payslip_earnings_sum", "payslip_net_pay")], ["warn", "warn"])
        self.assertEqual(self.status(payslip_checks({**payslip(), "net_pay": None}), "payslip_net_pay"), "warn")

    def test_pf_far_below_twelve_percent_warns(self):
        self.assertEqual(self.status(payslip_checks(payslip(net=37360.0, pf=640.0)), "pf_rate"), "warn")

    def test_professional_tax_by_state(self):
        self.assertEqual(expected_pt("Delhi", 50000), (False, 0))
        self.assertEqual(expected_pt("Maharashtra", 50000), (True, 200))
        self.assertEqual(expected_pt("Goa", 50000), (True, None))


class BankChecks(unittest.TestCase):
    def test_chain_reconciles(self):
        rows = [row(0, "2026-07-02", -100.0, 900.0), row(1, "2026-07-03", 500.0, 1400.0)]
        self.assertEqual(chain_breaks(1000.0, rows), [])
        self.assertTrue(all(c["status"] == "pass" for c in statement_checks(statement(rows))))

    def test_one_edited_balance_breaks_two_rows(self):
        rows = [row(0, "2026-07-02", -100.0, 900.0), row(1, "2026-07-03", 500.0, 11400.0), row(2, "2026-07-04", -100.0, 1300.0)]
        self.assertEqual([b["row"] for b in chain_breaks(1000.0, rows)], [1, 2])


class CrossDocument(unittest.TestCase):
    def test_salary_credit_found_in_window(self):
        rows = [row(0, "2026-08-28", 36080.0, 50000.0, "NEFT-SAL-NATARAJAN", "salary")]
        self.assertEqual(match_salary(payslip(), rows, set())["credit"]["row"], 0)
        self.assertIsNone(match_salary(payslip(net=46080.0), rows, set())["credit"])

    def test_emi_needs_two_months(self):
        rows = [row(0, "2026-07-05", -8500.0, 1, "NACH-DR-SURYA", "emi"), row(1, "2026-08-05", -8500.0, 1, "NACH-DR-SURYA", "emi"), row(2, "2026-08-09", -3000.0, 1, "NACH-DR-ONE-OFF", "emi"),
                row(3, "2026-09-01", 10.0, 1)]
        self.assertEqual([e["amount"] for e in recurring_emis(rows)], [8500.0])

    def test_only_latest_slip_jumps(self):
        slips = [payslip(month="2026-07"), payslip(month="2026-08"), payslip(month="2026-09", net=46080.0)]
        self.assertEqual([s["key"] for s in latest_month_signals(slips)], ["latest_month_edit"])

    def test_clean_applicant_is_verified(self):
        rows = [row(i, f"2026-{m:02d}-28", 36080.0, 1000.0 + 36080.0 * (i + 1), "NEFT-SAL-NATARAJAN", "salary") for i, m in enumerate((7, 8, 9))]
        docs = [{"doc_type": "payslip", "filename": f"p{m}.pdf", "fields": payslip(month=f"2026-{m:02d}"), "checks": [], "signals": [], "confidence": {"low": []}} for m in (7, 8, 9)]
        docs.append({"doc_type": "bank_statement", "filename": "b.pdf", "fields": statement(rows), "checks": [], "signals": [], "confidence": {"low": []}})
        result = analyze({"applicant_name": "Chaman Dara", "declared_employer": "Natarajan Pharma Pvt Ltd", "declared_monthly_income": 36080.0}, docs)
        self.assertEqual((result["status"], result["metrics"]["verified_monthly_income"]), ("verified", 36080.0), result["reasons"])

    def test_unreadable_net_pay_needs_review_not_flagged(self):
        # v1 false alarm: a phone photo lost its Net Pay line. Blank is a reading problem, not tampering.
        rows = [row(i, f"2026-{m:02d}-28", 36080.0, 1000.0 + 36080.0 * (i + 1), "NEFT-SAL-NATARAJAN", "salary") for i, m in enumerate((7, 8, 9))]
        slips = [payslip(month="2026-07"), payslip(month="2026-08"), payslip(month="2026-09", net=None)]
        docs = [{"doc_type": "payslip", "filename": f"p{i}.jpg", "fields": s, "checks": payslip_checks(s), "signals": [], "confidence": {"low": []}} for i, s in enumerate(slips)]
        docs.append({"doc_type": "bank_statement", "filename": "b.pdf", "fields": statement(rows), "checks": [], "signals": [], "confidence": {"low": []}})
        result = analyze({"applicant_name": "Chaman Dara", "declared_employer": "Natarajan Pharma Pvt Ltd", "declared_monthly_income": 36080.0}, docs)
        self.assertEqual(result["status"], "needs_review", result["reasons"])
        self.assertEqual([s["key"] for s in result["signals"]], [])


class Signals(unittest.TestCase):
    def test_late_large_credit(self):
        rows = [row(0, "2026-09-02", 1200.0, 2200.0, "IMPS-FRIEND", "transfer_in"), row(1, "2026-09-28", 250000.0, 252200.0, "IMPS-ANAY", "transfer_in")]
        self.assertEqual(len(window_dressing_signals(rows, "2026-09-30")), 1)

    def test_money_in_and_straight_out(self):
        rows = [row(0, "2026-09-02", 50000.0, 51000.0, "IMPS-X", "transfer_in"), row(1, "2026-09-03", -50000.0, 1000.0, "IMPS-X", "transfer_out")]
        self.assertEqual(len(circular_signals(rows)), 1)

    def test_repeats_of_one_signal_count_once(self):
        s = {"key": "odd_font", "weight": 20}
        self.assertEqual(authenticity([s, s]), 80)

    def test_summary_cannot_add_numbers(self):
        facts = {"verified_monthly_income": "₹36,080.00", "foir": "23.6%"}
        self.assertTrue(is_grounded("Income ₹36,080.00, FOIR 23.6%.", facts))
        self.assertFalse(is_grounded("Income ₹36,080.00, about ₹4,32,960 a year.", facts))


if __name__ == "__main__":
    unittest.main()
