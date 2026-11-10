# IncomeVerify: eval report (v2, 2026-11-06)

The current numbers. v1's full report, with ablations and the external set, is kept in `v1-report.md`.
Raw tables: `test3-v2.md` (headline), `dev-v2.md`, `test-v1.md` (per-applicant detail in the matching `.json`).

## Headline (fresh test set, v2, n=30)

A new split generated after the v2 fix (seed 3, `data/test3`), never run before the final pass: 30 synthetic
applicants, 150 documents (90 payslips, 23 of them phone photos; 30 bank statements; 30 Form 16s). 19 clean
(one with genuine EMI bounces that must *not* be flagged), 11 with one planted issue each across all 8 issue types.

| Metric | v2 |
|---|---:|
| Document type classification | 100% (150/150) |
| Field accuracy: payslip / bank header / Form 16 | 100% / 100% / 100% |
| Bank transactions P / R / F1 | 100% / 100% / 100% |
| Documents with every field right | 100% |
| Planted issues caught | **100% (11/11)**, every issue type |
| Auto-verified applicants that were truly clean | **100%** |
| Clean applicants wrongly flagged | **0 of 19** |
| Straight-through (clean → verified, no human) | **100%** |
| Verdict accuracy | 100% (30/30) |
| Verified income / EMI total / bounce count exact | 100% / 100% / 100% |
| Cross-check accuracy | 97.2% (see note) |
| Time per applicant p50 / p95 | 114 s / 132 s (documents read one after another) |
| Cost per applicant | **$0.053** |

**Note on cross-checks:** the 2.8% are scorer artefacts on three planted applicants. When only one document
carries the edit, the same check on the other documents correctly passes (for example the July and August salary
credits on an applicant whose September slip was edited), and the scorer counts those passes as misses. All three
applicants were caught and flagged. v1 had the same artefact.

## v1 → v2

| | v1 (test, seed 2) | v2 (test3, seed 3) |
|---|---:|---:|
| Planted issues caught | 11/11 | 11/11 |
| Clean applicants wrongly flagged | 2/19 | **0/19** |
| Straight-through | 89.5% | **100%** |
| Verdict accuracy | 93.3% | **100%** |
| Payslip field accuracy | 99.3% | 100% |
| Cost per applicant | $0.050 | $0.053 |

The two splits are different draws from the same generator, so this is v1 on its held-out set next to v2 on a
fresh one, not the same 30 applicants twice. On v1's set, v2 was checked on the two applicants it got wrong:
both now come out **verified** with authenticity 100.

## What changed in v2

v1's only errors were two clean applicants flagged as possible tampering. Both had a **phone-photo payslip**
where OCR lost the table layout: amounts shifted a row (gross and net pay blank) in one, the Net Pay line was
dropped in the other. The extractor correctly returned blank rather than guessing, but the checks then treated
"could not read" as "the maths is broken" (−30) and "no salary credit of — found" (a hard fail).

1. **A blank total is a warning, never a failed sum.** Tampering needs a value that is present and wrong.
   The salary match skips a payslip whose net pay could not be read instead of failing it.
2. **Image re-read of blank totals.** When a payslip total comes back blank, a different model reads the page
   image. Only blanks trigger it (a total that is present but wrong may be an edit, and is left to the checks),
   and the reading is kept only if every sum then adds up. On the fresh set it fired on 1 of 23 photos and was kept.

Dev set (n=10, the set used while building) after the change: 100% verdicts, 4/4 issues, 0 false alarms.
30 offline unit tests, including the three re-read rules with the model mocked.

## Limits, said plainly

- **Synthetic data.** The generator and the pipeline were written by the same person, so 100% here means the
  pipeline handles every layout and issue the generator makes, not every real-world document. The external set
  (30 real-layout scanned statements, `v1-report.md`) is the check against that: 98.9% transaction F1.
- **n=30.** One more error would move a headline number by about 3 points.
- The ablations (extraction model, OCR vs text layer) were measured on v1 and are not re-run; the change in v2
  does not touch extraction or OCR.

## Reproduce

```
cd income-verify-ml
python -m evals.run_evals --split dev --version v2
python -m data_gen.generate --split test3 --count 30 --seed 3
python -m evals.run_evals --split test3 --version v2
```
