"""The payslip image re-read: when it runs, and when its reading is kept. The model call is mocked; no network."""
import unittest
from unittest.mock import AsyncMock, patch
import reread


def raw_slip(gross="38,000.00", total="1,920.00", net="36,080.00"):
    return {"employee_name": "Chaman Dara", "employer_name": "Natarajan Pharma Pvt Ltd", "pay_month": "August 2026",
            "earnings": [{"name": "Basic Salary", "amount": "16,000.00"}, {"name": "Special Allowance", "amount": "22,000.00"}],
            "deductions": [{"name": "Provident Fund", "amount": "1,920.00"}], "gross_earnings": gross, "total_deductions": total, "net_pay": net, "page": 1}


def doc_from(raw):
    return {"doc_type": "payslip", "raw": raw, "fields": reread.normalize_payslip(raw)}


@patch.object(reread, "page_images", lambda data, filename: ["data:image/png;base64,AAAA"])
class PayslipReread(unittest.IsolatedAsyncioTestCase):
    async def test_blank_total_filled_and_kept_when_the_sums_pass(self):
        doc = doc_from(raw_slip(net=""))
        with patch.object(reread, "get_ai_output", AsyncMock(return_value=raw_slip())):
            result = await reread.reread_payslip(doc, b"", "slip.jpg", [{"page_number": 1, "markdown": ""}])
        self.assertEqual((result["fixed"], doc["fields"]["net_pay"]), (1, 36080.0))
        self.assertEqual(result["confirmed"], reread.PAYSLIP_TOTALS)

    async def test_reading_that_still_does_not_add_up_is_discarded(self):
        doc = doc_from(raw_slip(net=""))
        with patch.object(reread, "get_ai_output", AsyncMock(return_value=raw_slip(net="46,080.00"))):
            result = await reread.reread_payslip(doc, b"", "slip.jpg", [{"page_number": 1, "markdown": ""}])
        self.assertEqual((result["fixed"], doc["fields"]["net_pay"]), (0, None))

    async def test_present_but_wrong_total_is_never_reread(self):
        # An edited net pay is present and wrong: that is for the checks to flag, not for a second read to smooth over.
        model = AsyncMock()
        with patch.object(reread, "get_ai_output", model):
            result = await reread.reread_payslip(doc_from(raw_slip(net="46,080.00")), b"", "slip.pdf", [])
        self.assertIsNone(result)
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
