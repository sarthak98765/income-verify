# IncomeVerify v1: eval report (2026-11-03)

All numbers are from held-out data that was never used for tuning. Raw tables: `test-v1.md`, `test-v1-luna.md`,
`test-v1-sol.md`, `test-v1-textlayer.md`, `external-v1.1.md` (per-applicant detail in the matching `.json`).

- **Test set:** 30 synthetic applicants (seed 2), 150 documents: 90 payslips, 30 bank statements, 30 Form 16s.
  18 are clean, 1 has real EMI bounces (must *not* be flagged) and 11 carry one planted issue each across 8 issue
  types. 12 of 90 payslips are phone photos.
- **External set:** 30 scanned AgamiAI statements (Hugging Face, Apache-2.0), 180 pages, 4,841 transactions, in two
  layouts we never designed for or looked at while building.
- **Pipeline v1:** Mistral OCR → gpt-6-luna classify → gpt-6.1-terra extract → Python checks, cross-checks, verdict.

## Headline (test set, v1, n=30)

| Metric | Value |
|---|---:|
| Document type classification | 100% (150/150) |
| Field accuracy: payslip / bank header / Form 16 | 99.3% / 100% / 100% |
| Bank transactions P / R / F1 | 100% / 100% / 100% |
| Documents with every field right | 98.7% |
| Planted issues caught | **100% (11/11)**, every issue type |
| Auto-verified applicants that were truly clean | **100%** (no fraud passed as verified) |
| Clean applicants wrongly flagged | 2 of 19 (10.5%) |
| Straight-through (clean → verified, no human) | 89.5% |
| Cross-check accuracy | 96.5% |
| Verified income / EMI total / bounce count exact | 100% / 100% / 100% |
| Verdict accuracy | 93.3% (28/30) |
| Time per applicant p50 / p95 | 106 s / 121 s (documents read one after another) |
| Time per document p50: payslip / Form 16 / bank statement | 7 s / 7 s / 77 s |
| Cost per applicant | **$0.050** (OCR $0.007 + LLM $0.043) |

## External set (unseen layouts, v1.1, n=30 statements)

| Metric | All | Type 1 (debit/credit columns) | Type 2 (signed amount) |
|---|---:|---:|---:|
| Classified as bank statement | 100% | 100% | 100% |
| Header fields (holder, opening, closing) | 100% | 100% | 100% |
| Transaction F1 (date, debit, credit, balance all exact) | **98.9%** | 98.8% | 99.0% |
| Statements with every row exact | 73.3% | 60.0% | 86.7% |
| Balance check flags exactly the truly-breaking rows | 73.3% | 60.0% | 86.7% |
| Time / cost per 6-page statement | 163 s / $0.126 | | |

- Every statement had the right number of rows. The 53 wrong rows (1.1%) are single-digit misreads in the scans
  (6↔8, 1↔2). **43 of them (81%) broke the balance chain and were flagged for review**; 10 slipped through.
- AgamiAI's own printed balances do not add up around reversals and failed debits (all 30 statements). On the 22
  statements read perfectly, our balance check flagged exactly those rows and no others.
- The pilot found a real bug: dates printed with a time ("01-01-2024 11:30:55") came out empty. Fixed in
  `utils.parse_date` with a test (v1 → v1.1); the synthetic test set has no such dates, so its numbers are unchanged.

## Ablations (test set, n=30)

| Variant | Planted issues caught | False alarms | Straight-through | Payslip fields | Cost per applicant |
|---|---:|---:|---:|---:|---:|
| **v1: Mistral OCR + gpt-6.1-terra extract** | 11/11 | 2/19 | 89.5% | 99.3% | $0.050 |
| gpt-6-luna extract (cheaper) | 11/11 | 2/19 | 89.5% | 99.4% | **$0.012** |
| gpt-6.1-sol extract (stronger) | 11/11 | 2/19 | 89.5% | 99.3% | $0.093 |
| PDF text layer instead of OCR | 9/11 | 0/19 | 21.1% | 100%¹ | $0.030 |

Cost = LLM cost of the run + v1's OCR cost ($0.007), because OCR is cached by content and was not re-paid.
Ablation run times exclude OCR for the same reason, so they are not compared.

¹ Only on the documents it could classify: 27% of documents (every photo and scanned PDF) have no text layer, so
classification drops to 73.3% and most clean applicants end in "needs review".

**What they show**
- **The extraction model is not the bottleneck.** luna, terra and sol score the same on every metric; luna's LLM cost
  is ~8× lower than terra's and ~17× lower than sol's. Switching extraction to luna would cut the cost per applicant from
  $0.050 to about $0.012 (decision pending; it was measured on the test set, so confirm it on a fresh split).
- **OCR is worth paying for.** Without it every phone photo and scan is unreadable: straight-through falls from
  89.5% to 21.1% and 2 planted issues are missed.
- **Re-read step:** it fired on 2 of 30 statements, both with a genuinely edited balance, and correctly changed
  nothing (the break was printed, not misread). A "no re-read" run would match v1 exactly, so it was not run.

## Errors, explained

Both false alarms (APP2008, APP2019) are clean applicants with a **phone-photo payslip** where OCR lost the
table layout: in one, every amount shifted up a row so "Gross" and "Net pay" were blank; in the other the Net Pay
line was dropped. The extractor correctly returned blank instead of guessing (which is why luna, terra and sol
all agree), but the checks then treated "could not read" as "the math is broken" and flagged the applicant as
possible tampering. Both were caught by the checks; they just landed in the wrong bucket.

**Fix for v2 (not applied, to keep the test set honest):**
1. A field the model could not read → **needs review**, never **flagged**. Tampering needs a value that is present
   and wrong.
2. When a photo or scan fails its payslip math, re-read that page with a vision model (the same idea as the bank
   statement re-read).

Then confirm on dev and on a fresh test split (seed 3), and report v2 next to v1.

## Reproduce

```
cd income-verify-ml
python -m data_gen.generate --split test --count 30 --seed 2
python -m evals.run_evals --split test --version v1
python -m evals.run_evals --split test --version v1-luna --extract-model gpt-6-luna
python -m evals.run_evals --split test --version v1-sol --extract-model gpt-6.1-sol
python -m evals.run_evals --split test --version v1-textlayer --reader textlayer
python -m evals.external --count 15 --version v1.1
```
