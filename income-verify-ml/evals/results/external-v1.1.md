### IncomeVerify v1.1 (external AgamiAI scanned statements, extract=gpt-6.1-terra) · n=30

| Metric | All | Type 1 (debit/credit columns) | Type 2 (signed amount column) |
|---|---:|---:|---:|
| Statements / pages / rows | 30 / 180 / 4841 | 15 / 90 / 2423 | 15 / 90 / 2418 |
| Classified as bank statement | 100.0% | 100.0% | 100.0% |
| Header: account_holder | 100.0% | 100.0% | 100.0% |
| Header: opening_balance | 100.0% | 100.0% | 100.0% |
| Header: closing_balance | 100.0% | 100.0% | 100.0% |
| Transaction precision | 98.9% | 98.8% | 99.0% |
| Transaction recall | 98.9% | 98.8% | 99.0% |
| Transaction F1 | 98.9% | 98.8% | 99.0% |
| Statement exact (header + every row) | 73.3% | 60.0% | 86.7% |
| Statements whose printed balances truly break | 30 of 30 | 15 of 15 | 15 of 15 |
| Balance check flags exactly the breaking rows | 73.3% | 60.0% | 86.7% |
| Time per statement p50 / p95 | 162.55s / 201.1s | 187.0s / 201.1s | 151.2s / 161.5s |
| Cost per statement | $0.1262 | $0.1373 | $0.1150 |

Rows match on (date, debit, credit, balance).
