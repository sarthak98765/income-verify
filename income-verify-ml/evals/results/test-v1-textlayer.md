### IncomeVerify v1-textlayer (test, extract=gpt-6.1-terra, PDF text layer) · n=30 applicants, 150 documents

| Metric | Value |
|---|---:|
| Document classification | 73.3% |
| Payslip field accuracy | 100.0% |
| Bank header field accuracy | 100.0% |
| Form 16 field accuracy | 100.0% |
| Transaction P / R / F1 | 100.0% / 100.0% / 100.0% |
| Balance chain reconciles (unedited statements) | 100.0% |
| Document exact match (every field right) | 100.0% |
| Cross-check accuracy | 97.4% |
| Verdict accuracy | 46.7% |
| Issue catch rate | 81.8% (9/11) |
| False alarms on clean applicants (flagged) | 0.0% |
| Straight-through (clean → verified) | 21.1% |
| Auto-verified that were truly clean | 100.0% |
| Verified income exact | 73.3% |
| EMI total exact | 86.7% |
| Bounce count exact | 100.0% |
| Time per applicant p50 / p95 | 82.7s / 93.3s |
| Cost per applicant | $0.0295 |

**Catch rate by planted issue**

| Issue | Caught |
|---|---:|
| balance_edited | 1/2 |
| fake_credit | 1/1 |
| form16_mismatch | 1/1 |
| name_mismatch | 1/1 |
| net_pay_edited | 2/2 |
| pdf_edited | 1/1 |
| salary_mismatch | 1/2 |
| statutory | 1/1 |

Verdicts (expected → got): {'needs_review→needs_review': 3, 'verified→needs_review': 15, 'flagged→flagged': 7, 'verified→verified': 4, 'flagged→needs_review': 1}

**Per document** (time is sequential processing of one document)

| Type | n | Exact match | Time p50 / p95 | Cost |
|---|---:|---:|---:|---:|
| all | 110 | 100.0% | 3.9s / 75.0s | $0.0080 |
| payslip | 68 | 100.0% | 3.9s / 4.4s | $0.0018 |
| bank_statement | 21 | 100.0% | 71.5s / 82.5s | $0.0343 |
| form16 | 21 | 100.0% | 3.1s / 3.4s | $0.0017 |

**Per field**

| Document | Field | Accuracy |
|---|---|---:|
| payslip | employee_name | 100.0% |
| payslip | employer_name | 100.0% |
| payslip | month | 100.0% |
| payslip | gross | 100.0% |
| payslip | total_deductions | 100.0% |
| payslip | net_pay | 100.0% |
| bank_statement | account_holder | 100.0% |
| bank_statement | opening_balance | 100.0% |
| bank_statement | closing_balance | 100.0% |
| form16 | employee_pan | 100.0% |
| form16 | gross_salary | 100.0% |
| form16 | standard_deduction | 100.0% |
| form16 | taxable_income | 100.0% |
| form16 | regime | 100.0% |
