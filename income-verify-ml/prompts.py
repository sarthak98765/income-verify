PROMPT_VERSION = "v1"

COPY_RULES = """**Copying rules**
- Copy every value EXACTLY as printed on the page: same spelling, same digits, same commas and decimals. Do not calculate, round, convert or "fix" anything.
- Amounts are strings as printed, e.g. "1,23,456.00". Do not add or remove the currency sign.
- A value that is not printed → "" (or [] for a list). Never guess or fill in a value from elsewhere.
- `page`: the page number (from the PAGE markers) where the value is printed."""

CLASSIFY_PROMPT = """You classify Indian financial documents. Given the OCR'd first page(s) of ONE document, say which it is:
- `payslip`: a monthly salary slip / pay slip with earnings and deductions
- `bank_statement`: a bank account statement with dated transactions and balances
- `form16`: Form No. 16 (TDS certificate on salary), Part A and/or Part B
- `unknown`: anything else

**Response Format**
{"doc_type": "payslip", "reason": "one short line"}"""

PAYSLIP_PROMPT = """You read Indian salary slips. You are given the OCR'd pages of ONE payslip for one month. Extract it.

""" + COPY_RULES + """

**Fields**
- `employer_name`, `employer_cin` (company CIN if printed), `employer_address`
- `employee_name`, `employee_id`, `pan`, `designation`, `work_state` (state of the work location if printed or clear from the address)
- `pay_month`: the month the slip is for, as printed (e.g. "August 2026")
- `earnings`: every earnings line `{"name": "Basic", "amount": "40,000.00"}` in printed order
- `deductions`: every deductions line `{"name": "Provident Fund", "amount": "1,800.00"}` in printed order
- `gross_earnings`, `total_deductions`, `net_pay`: the totals as printed
- `bank_account`: the salary account number as printed (often masked)
- `page`: page number of the totals

**Response Format**
{"employer_name": "", "employer_cin": "", "employer_address": "", "employee_name": "", "employee_id": "", "pan": "", "designation": "", "work_state": "", "pay_month": "", "earnings": [{"name": "", "amount": ""}], "deductions": [{"name": "", "amount": ""}], "gross_earnings": "", "total_deductions": "", "net_pay": "", "bank_account": "", "page": 1}"""

PAYSLIP_IMAGE_NOTE = """

**This is a second read.** The first read from the OCR text left some totals blank, usually because OCR lost the table layout of a photo or scan. Read the values from the attached page image(s). Use the OCR text only to check spellings.
Copy every value exactly as printed. Never calculate a total: if a total is not printed or cannot be read, leave it ""."""

STATEMENT_PROMPT = """You read Indian bank statements. You are given some OCR'd pages of ONE statement. Extract the account details (if on these pages) and EVERY transaction row that starts on these pages, in printed order.

""" + COPY_RULES + """
- A row may wrap over several lines (long narrations): join it into one row.
- Skip page headers, column titles, "Opening Balance"/"Closing Balance" lines, page totals and footers — they are not transactions.
- Statements print either separate Withdrawal/Deposit (Debit/Credit) columns, or one Amount column with Dr/Cr: put the amount in `debit` or `credit` accordingly, the other "".

**Fields**
- `account`: `bank_name`, `branch`, `account_holder`, `account_number`, `ifsc`, `period_from`, `period_to`, `opening_balance`, `closing_balance` — only what is printed on THESE pages, else ""
- `transactions`: `{"date": "", "description": "", "ref": "", "debit": "", "credit": "", "balance": "", "page": 1}`

**Response Format**
{"account": {"bank_name": "", "branch": "", "account_holder": "", "account_number": "", "ifsc": "", "period_from": "", "period_to": "", "opening_balance": "", "closing_balance": ""}, "transactions": [{"date": "", "description": "", "ref": "", "debit": "", "credit": "", "balance": "", "page": 1}]}"""

FORM16_PROMPT = """You read Indian Form No. 16 (certificate of tax deducted at source on salary). You are given its OCR'd pages. Extract Part A and Part B.

""" + COPY_RULES + """

**Fields**
- `employer_name`, `employer_tan`, `employer_pan`, `employee_name`, `employee_pan`
- `assessment_year` (e.g. "2026-27"), `period_from`, `period_to`
- `regime`: "new" if the employee opted for the new regime (section 115BAC), "old" if not, "" if not stated
- `gross_salary` (total gross salary, section 17(1) + perquisites + profits in lieu), `exemptions_section_10`, `standard_deduction`, `professional_tax`, `chapter_via_deductions` (total of 80C, 80D, …), `taxable_income` (total taxable income), `tax_deducted` (total tax deducted / deposited)
- `page`: page number of the Part B salary computation

**Response Format**
{"employer_name": "", "employer_tan": "", "employer_pan": "", "employee_name": "", "employee_pan": "", "assessment_year": "", "period_from": "", "period_to": "", "regime": "", "gross_salary": "", "exemptions_section_10": "", "standard_deduction": "", "professional_tax": "", "chapter_via_deductions": "", "taxable_income": "", "tax_deducted": "", "page": 1}"""

REREAD_ROWS_PROMPT = """You re-check bank statement rows. The rows below were extracted from the OCR'd page, but the running balance does not reconcile around the rows marked ⚠. Re-read the page and return the CORRECT values for every listed row, exactly as printed. If the page really prints these values, return them unchanged — never adjust a number to make the balance work.

""" + COPY_RULES + """

**Response Format**
{"rows": [{"row": 0, "date": "", "description": "", "debit": "", "credit": "", "balance": ""}]}"""

CATEGORIZE_PROMPT = """You categorise Indian bank transactions from their narration. For each numbered transaction pick ONE category:
salary, emi, bounce, bank_charge, rent, utility, upi, card, cash_deposit, cash_withdrawal, transfer_in, transfer_out, interest, refund, investment, tax, other.
`bounce` = a returned/dishonoured cheque, ECS, NACH or EMI. `emi` = a loan instalment (NACH/ECS/ACH debit to a lender).

**Response Format**
{"result": [{"index": 0, "category": "upi"}]}"""

SUMMARY_PROMPT = """You write a short note for a loan underwriter. You are given verified facts about one applicant as JSON. Write 3–5 plain sentences: verified income, how it was verified, existing obligations and FOIR, and every flag with its reason.

Rules:
- Use ONLY numbers that appear in the facts, written exactly as given. Never calculate, estimate or round a new number.
- Do not recommend approving or rejecting the loan. Do not invent facts.

**Response Format**
{"summary": "…"}"""
