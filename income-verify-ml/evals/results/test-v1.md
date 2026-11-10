### IncomeVerify v1 (test, extract=gpt-6.1-terra) · n=30 applicants, 150 documents

| Metric | Value |
|---|---:|
| Document classification | 100.0% |
| Payslip field accuracy | 99.3% |
| Bank header field accuracy | 100.0% |
| Form 16 field accuracy | 100.0% |
| Transaction P / R / F1 | 100.0% / 100.0% / 100.0% |
| Balance chain reconciles (unedited statements) | 100.0% |
| Document exact match (every field right) | 98.7% |
| Cross-check accuracy | 96.5% |
| Verdict accuracy | 93.3% |
| Issue catch rate | 100.0% (11/11) |
| False alarms on clean applicants (flagged) | 10.5% |
| Straight-through (clean → verified) | 89.5% |
| Auto-verified that were truly clean | 100.0% |
| Verified income exact | 100.0% |
| EMI total exact | 100.0% |
| Bounce count exact | 100.0% |
| Time per applicant p50 / p95 | 106.05s / 121.3s |
| Cost per applicant | $0.0503 |

**Catch rate by planted issue**

| Issue | Caught |
|---|---:|
| balance_edited | 2/2 |
| fake_credit | 1/1 |
| form16_mismatch | 1/1 |
| name_mismatch | 1/1 |
| net_pay_edited | 2/2 |
| pdf_edited | 1/1 |
| salary_mismatch | 2/2 |
| statutory | 1/1 |

Verdicts (expected → got): {'needs_review→needs_review': 3, 'verified→verified': 17, 'flagged→flagged': 8, 'verified→flagged': 2}

**Per document** (time is sequential processing of one document)

| Type | n | Exact match | Time p50 / p95 | Cost |
|---|---:|---:|---:|---:|
| all | 150 | 98.7% | 7.2s / 83.0s | $0.0101 |
| payslip | 90 | 97.8% | 7.2s / 9.0s | $0.0029 |
| bank_statement | 30 | 100.0% | 77.3s / 90.4s | $0.0387 |
| form16 | 30 | 100.0% | 6.9s / 7.5s | $0.0028 |

**Per field**

| Document | Field | Accuracy |
|---|---|---:|
| payslip | employee_name | 100.0% |
| payslip | employer_name | 100.0% |
| payslip | month | 100.0% |
| payslip | gross | 98.9% |
| payslip | total_deductions | 98.9% |
| payslip | net_pay | 97.8% |
| bank_statement | account_holder | 100.0% |
| bank_statement | opening_balance | 100.0% |
| bank_statement | closing_balance | 100.0% |
| form16 | employee_pan | 100.0% |
| form16 | gross_salary | 100.0% |
| form16 | standard_deduction | 100.0% |
| form16 | taxable_income | 100.0% |
| form16 | regime | 100.0% |
