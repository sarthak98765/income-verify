# IncomeVerify: load test (2026-11-06)

Everything ran on one laptop (Apple Silicon): Postgres and RabbitMQ in Docker, the API as one Node process, the ML
worker as 2 Python processes (`WORKER_CONCURRENCY = 2`). Real OpenAI and Mistral calls. Raw output in `results/`.

## API (k6, `api.js`)

The read endpoints the UI polls: the applications list (40% of requests), an application (35%), a document (15%),
stats (10%). Each virtual user sends its own `X-Forwarded-For`, as real visitors do through the proxy, so the
per-IP rate limiter sees separate people.

| Run | Load | Requests | p50 | p95 | p99 | Errors |
|---|---|---:|---:|---:|---:|---:|
| Browsing | ramp to 50 users, each polling every 1–2 s, 3 min 20 s | 4,817 (24/s) | 3 ms | 15 ms | 22 ms | 0% |
| Stress | 100 users, no pause, 60 s | 105,614 (**1,758/s**) | 59 ms | 89 ms | 105 ms | 0% |

Per endpoint in the stress run, p95: list 52 ms, application 96 ms, document 95 ms, stats 78 ms.

The first stress run returned 97% errors: every user hit the rate limit (600 requests per 15 min per IP) within
seconds, which is the limiter working. The run above gives each user a new address every 500 requests, so it
measures the API, not the limiter. The API is not the bottleneck: a demo would need a few requests a second.

## Pipeline (`pipeline.mjs`)

N applicants uploaded at the same moment through the real path (create → upload → queue → worker → verdict), each
with 3 payslips (some phone photos), a 6-month bank statement and Form 16. **Fresh synthetic files** (`data/load`,
seed 4) that had never been read, so OCR was not served from cache.

| At once | Time to verdict, p50 | p95 | Whole batch | Throughput | Verdicts right | AI cost |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 105 s | 105 s | 105 s | 34 / hour | 1/1 | $0.058 |
| 5 | 370 s | 373 s | 373 s | 48 / hour | 5/5 | $0.244 |
| 10 | 707 s | 719 s | 719 s | **50 / hour** | 10/10 | $0.496 |

16 of 16 verdicts right on the fresh files, about $0.05 per applicant.

**What it shows**

- **Throughput is set by the worker count.** With 2 workers it levels off at about 50 applicants an hour. The work
  is waiting on OCR and model APIs, not on CPU, so more worker processes (`WORKER_CONCURRENCY`) or a second
  machine should scale it close to linearly. That is the next thing to measure, not a claim.
- **Everyone in a burst waits for the whole burst.** The queue is first in, first out by document, so 10
  applicants' 50 documents are read interleaved and all ten verdicts land near the end (p50 ≈ the whole batch).
  For a lender, finishing one file before starting the next is better: the first verdict would come after about
  2 minutes instead of 12. Fix for later: a per-application priority, or one queue message per application.
- **One applicant alone takes about 105 s,** almost all of it the bank statement (OCR of 6 pages, extraction in
  page batches, the balance check). Payslips and Form 16 take about 8 s each.

## Reproduce

```
# API: a backend that trusts X-Forwarded-For, on its own port (same database)
cd income-verify-backend && NODE_ENV=production APP_PORT=5940 TRUST_PROXY=1 node src/app.js
cd .. && k6 run loadtest/api.js && STRESS=1 k6 run loadtest/api.js

# Pipeline: fresh applicants, then batches of 1, 5 and 10 against the running stack (costs about $0.85)
cd income-verify-ml && python -m data_gen.generate --split load --count 16 --seed 4
cd .. && node loadtest/pipeline.mjs 1 5 10
```
