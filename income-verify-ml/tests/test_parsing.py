"""Parsing helpers and the JSON repair between the model and the pipeline.

Run from income-verify-ml:  python -m unittest discover tests
No network, no database, no API keys.
"""
import unittest
from extraction import drop_duplicates, merge_account, normalize_payslip
from utils import extract_json, names_match, parse_amount, parse_date, parse_month


class ParseAmount(unittest.TestCase):
    def test_indian_grouping_and_symbols(self):
        self.assertEqual(parse_amount("₹1,23,456.50"), 123456.5)
        self.assertEqual(parse_amount("Rs. 45,000"), 45000.0)
        self.assertEqual(parse_amount("INR 2,04,15.00"), 20415.0)

    def test_debit_markers_and_blanks(self):
        self.assertEqual(parse_amount("1,200.00 Dr"), -1200.0)
        self.assertEqual(parse_amount("(500.00)"), -500.0)
        self.assertEqual(parse_amount("1,200.00 Cr"), 1200.0)
        for blank in ["", "-", None, "N/A"]:
            self.assertIsNone(parse_amount(blank), blank)


class ParseDates(unittest.TestCase):
    def test_statement_formats(self):
        for raw in ["05/08/2026", "05-08-2026", "05-Aug-2026", "05 Aug 2026", "05-08-26", "05/08/26", "2026-08-05"]:
            self.assertEqual(parse_date(raw), "2026-08-05", raw)

    def test_date_with_time(self):
        for raw in ["05-08-2026 11:30:55", "05/08/2026 12:12:52 PM", "05-Aug-2026 09:05"]:
            self.assertEqual(parse_date(raw), "2026-08-05", raw)

    def test_pay_months(self):
        for raw in ["August 2026", "Aug 2026", "Aug-26", "08/2026", "2026-08"]:
            self.assertEqual(parse_month(raw), "2026-08", raw)


class Names(unittest.TestCase):
    def test_same_person_in_different_forms(self):
        self.assertTrue(names_match("Rahul Sharma", "RAHUL SHARMA", 85))
        self.assertTrue(names_match("Rahul Sharma", "Mr. Sharma Rahul", 85))
        self.assertTrue(names_match("Rahul Kumar Sharma", "R K Sharma", 85))

    def test_different_people(self):
        self.assertFalse(names_match("Rahul Sharma", "Rohit Verma", 85))
        self.assertFalse(names_match("Rahul Sharma", "Rahul Mehta", 85))


class ModelOutput(unittest.TestCase):
    def test_json_in_fences_or_prose(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json('Here you go: {"a": {"b": "x}"}} thanks'), {"a": {"b": "x}"}})

    def test_payslip_normalisation_tolerates_nulls(self):
        f = normalize_payslip({"employee_name": None, "pay_month": "July 2026", "net_pay": "36,080.00", "earnings": [{"name": "Basic", "amount": "16,000.00"}, {"name": None}]})
        self.assertEqual((f["employee_name"], f["month"], f["net_pay"], len(f["earnings"])), ("", "2026-07", 36080.0, 1))

    def test_boundary_row_read_twice_is_dropped(self):
        row = {"date": "2026-08-01", "debit": 100.0, "credit": None, "balance": 900.0}
        self.assertEqual(len(drop_duplicates([row, dict(row), {**row, "balance": 800.0}])), 2)

    def test_account_details_merge_across_batches(self):
        merged = merge_account([{"bank_name": "Narmada Bank", "closing_balance": ""}, {"bank_name": "", "closing_balance": "45,365.02"}])
        self.assertEqual((merged["bank_name"], merged["closing_balance"]), ("Narmada Bank", "45,365.02"))


if __name__ == "__main__":
    unittest.main()
