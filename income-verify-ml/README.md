# income-verify-ml

RabbitMQ worker for IncomeVerify. It has no public API: the backend reaches it only through the queue. The only HTTP it serves is a `/health` probe.

## What it does

Two tasks, dispatched from `{"task", "id"}` on `main_queue`, one row of `TASKS` in `worker.py` each:

| Task | Row | Pipeline |
|---|---|---|
| `process_document` | `documents` | stored file → Mistral OCR (cached by hash) → classify (keywords, model only if unsure) → extract (payslip / bank statement / Form 16) → bank: categorise rows, re-read rows whose balance doesn't reconcile → checks → tamper signals → per-field confidence |
| `analyze_application` | `applications` | re-run checks on (possibly reviewer-corrected) fields → salary credit vs payslip, names, employer, annual income → metrics (income, EMIs, bounces, FOIR, balances) → verdict + authenticity score → underwriter note |

When the last document of an application finishes, the worker queues `analyze_application` itself. Every parameter lives on the row, so messages stay tiny and a redelivery is safe. Failures go main → `retry_queue` (15 s TTL, dead-letters back to main) → after `MAX_RETRIES`, `dlq_queue` with the row marked failed. `requeue_dlq.py` moves them back.

**The rule:** the model reads; Python does every sum, match and decision. The model never computes a number, and the underwriter note is rejected if it contains a number that isn't in the computed facts.

## Layout

```
config.py        secrets from env, everything else as literals (models, prices, tolerances, PT slabs, signal weights)
logger.py        stdout logger, "module | message"
health.py        /health on a daemon thread; HEALTH_PORT=0 disables it
storage.py       local disk under STORAGE_DIR (shared with the backend), async wrappers
db.py            asyncpg pool with JSON codecs; update() helper
usage.py         per-task spend (contextvar tally): tokens, $ by model, OCR pages
progress.py      per-task progress → <table>.progress (the UI polls it)
ai_client.py     the ONE place an LLM is called: retries, then one round on a fallback model, rejected-param fallback, JSON mode, halving on truncation
tracing.py       Langfuse traces over its ingestion API: one trace per task, one generation per call; off without keys
prompts.py       one prompt per task; values copied as printed, never calculated
ocr.py           Mistral OCR: upload → OCR → delete; empty/looping pages re-read as images; cache by sha256
classify.py      keyword rules first, cheap model only when unsure
extraction.py    payslip / statement (page batches + context page, boundary de-dup) / Form 16 → normalised fields
categorize.py    transaction categories: narration rules first, cheap model for leftovers
reread.py        targeted re-reads by a different model: bank rows that break the balance chain, payslip totals left blank (from the page image)
checks.py        inside one document: payslip math + statutory (PF, ESI, PT), balance chain, Form 16 math
tamper.py        PDF metadata, odd fonts, round amounts, window dressing, circular money → authenticity score
confidence.py    per field: grounded in OCR text + no check doubts it + page read cleanly
analysis.py      across documents: salary credits, identity, employer, annual income, metrics, verdict
summary.py       underwriter note from pre-formatted facts, number-checked
pipeline.py      process_document / analyze_application, free of queue and DB (worker, run_local and evals share it)
tasks.py         the DB side of each task
worker.py        consumer, retry ladder, usage_log, queues the analysis when an application's documents are done
requeue_dlq.py   ops: move dead-lettered messages back
run_local.py     run a folder of documents without queue or DB
data_gen/        synthetic applicants with ground truth (profiles → 6-month bank simulation → PDF templates → scans/photos → planted issues)
evals/           run_evals.py (cached per applicant) + score.py; external.py (AgamiAI statements); results/*.md
tests/           unittest, no network
```

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # or: uv venv && uv pip install -r requirements.txt
# keys (OPENAI_API_KEY, MISTRAL_API_KEY) are read from the repo-root .env

python -m unittest discover tests                      # offline tests
python -m data_gen.generate --split dev --count 10 --seed 1
python run_local.py data/dev/APP1003                   # one applicant, no queue/DB
python -m evals.run_evals --split dev --version v1     # score against ground truth
python -m evals.external --count 15 --version v1.1     # AgamiAI scanned statements (downloads ~190 MB)

# with the stack (from projects/income-verify): docker compose up -d postgres rabbitmq
python worker.py
```

Local ports avoid clashing with Homebrew services: Postgres `5434`, RabbitMQ `5674` (management `15674`).

## Models (config.py)

| Step | Model | Why |
|---|---|---|
| OCR | `mistral-ocr-latest` (~$1 / 1,000 pages) | tables as markdown, handles scans and photos |
| Classify (rarely) | `gpt-6-luna` | tiny task, cheapest |
| Extract | `gpt-6.1-terra` | strong structured output on long tables; in the v1 evals luna and sol score the same (luna ~8× cheaper) |
| Re-read broken rows, blank payslip totals | `gpt-6.1-sol` | rare and targeted; a *different* model from the extractor |

If a model still fails after its retries (outage, rate limit, timeout), the call gets one more round on its fallback (`FALLBACK_MODELS`: terra ↔ sol, luna → terra), counted as `fallbacks` in the task's usage. Truncation never falls back; the input is halved instead.

Tracing: set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (and `LANGFUSE_HOST` for a non-EU region) in the repo-root `.env`. Every call is then traced with its name, model, tokens, cost, latency and any error.
| Categorise leftovers, summary | `gpt-6-luna` | cheap rewording / labelling |

## Results (v2, fresh held-out test set)

30 synthetic applicants, 150 documents, never used while building: 11/11 planted issues caught, 0/19 clean applicants
wrongly flagged, 100% straight-through, $0.053 per applicant. Report with the v1 → v2 change and its limits:
[`evals/results/report.md`](evals/results/report.md). v1's ablations and the external set: [`evals/results/v1-report.md`](evals/results/v1-report.md).
