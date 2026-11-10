# income-verify-backend

Express API for IncomeVerify. It stores uploads on local disk (`../storage`, shared with the ML worker), writes
Postgres rows (`applications`, `documents`, `field_edits`), and publishes `{task, id}` to RabbitMQ for the worker.
It never runs a model: everything the worker computes is read back from the rows.

```
npm install
npm test            # offline: edits, upload guards, validation, export
npm run dev         # :5920 (needs Postgres + RabbitMQ: docker compose up -d postgres rabbitmq)
```

Defaults match `docker-compose.yml` (Postgres 5434, RabbitMQ 5674), so no `.env` is needed locally; see
`.env.example` to override. The schema is `migrations/001_init.sql`, applied by Postgres on first start.

## Endpoints

| Method | Path | Does |
|---|---|---|
| POST | `/applications` | create (applicant_name, declared_employer, declared_monthly_income) |
| GET | `/applications` | list with status, verdict numbers and document counts (`?status=&q=&limit=`) |
| GET | `/applications/:id` | detail: documents, checks, metrics, summary, progress, cost and time totals |
| POST | `/applications/:id/documents` | upload files (`files`, multipart) → queue `process_document` each |
| POST | `/applications/:id/analyze` | queue `analyze_application` again (e.g. after a failure) |
| POST | `/applications/:id/approve` | final sign-off; fields are locked after |
| GET | `/applications/:id/export?format=json\|xlsx` | export |
| DELETE | `/applications/:id` | delete with its files |
| GET | `/documents/:id` | fields, confidence, checks, signals, progress, edit history |
| GET | `/documents/:id/file` | the original file, for the viewer |
| PATCH | `/documents/:id/fields` | `{edits: [{path, value}]}` → audit in `field_edits` → queue `analyze_application` |
| GET | `/samples` | synthetic applicants (from `income-verify-ml/data/dev`) |
| POST | `/samples/:key` | create an application from one and queue it |
| GET | `/stats` | documents read, straight-through %, average cost and time, eval headline |
| GET | `/health` | liveness |

Guards: a Cloudflare Turnstile bot check on creating applications, uploads and samples (when `TURNSTILE_SECRET_KEY` is set); PDF/PNG/JPG/WEBP only, checked by content not just extension; 15 MB and 30 pages per file; 10 files per
upload, 20 per application; per-IP rate limits (stricter on uploads and samples); zod validation; JSON errors
that never leak a stack in production; applications older than `RETENTION_HOURS` (24) are deleted with their files.

## Layout

```
src/app.js           routes, rate limit, error handler, cleanup timer
src/config.js        .env for deployment values, literals for everything else
src/db.js            pg pool (numeric → number), one / all / tx helpers
src/publisher.js     RabbitMQ publish with confirms (never declares queues)
src/jobs.js          queue a document or an analysis; mark the row failed if the broker is down
src/storage.js       local disk under STORAGE_DIR; keys can't escape it
src/upload.js        multer, content sniffing, PDF page count
src/validate.js      zod schemas
src/applications.js  load applications/documents, add uploaded documents, delete
src/fields.js        apply reviewer edits to extracted fields (dot paths)
src/export.js        JSON and xlsx export
src/samples.js       synthetic applicants from data_gen
src/cleanup.js       24 h retention sweep
src/routes/          applications, documents, samples, stats
```

Edits change only the extracted values; the worker re-runs every check and recomputes the verdict. The one
thing derived here is a transaction's signed `amount` from its debit and credit, so the balance check sees the fix.
