const crypto = require('crypto')
const db = require('./db')
const storage = require('./storage')
const { queueDocuments } = require('./jobs')
const { checkFile, safeName, extOf } = require('./upload')
const { FILE_TYPES, MAX_DOCUMENTS_PER_APPLICATION } = require('./config')
const { HttpError } = require('./middleware/error')

/** Loading applications and their documents, shared by the routes, samples and export. */

const ACTIVE = ['queued', 'processing']

async function findApplication(id) {
  const app = await db.one('SELECT * FROM applications WHERE id = $1', [id])
  if (!app) throw new HttpError(404, 'Application not found')
  return app
}

// The few fields that identify a document in a list, so the detail page needs no `fields` payload.
function facts(doc) {
  const f = doc.fields || {}
  if (doc.doc_type === 'payslip') return { month: f.month, net_pay: f.net_pay, gross: f.gross, employer: f.employer_name }
  if (doc.doc_type === 'bank_statement') return { bank: f.account?.bank_name, period_from: f.account?.period_from, period_to: f.account?.period_to, transactions: f.transactions?.length || 0 }
  if (doc.doc_type === 'form16') return { assessment_year: f.assessment_year, gross_salary: f.gross_salary, employer: f.employer_name }
  return {}
}

async function listDocuments(applicationId) {
  const rows = await db.all(
    `SELECT id, filename, mime, size_bytes, status, doc_type, classified_by, pages, low_quality_pages, fields, checks, signals,
            confidence, progress, usage, error, created_at, updated_at
       FROM documents WHERE application_id = $1 ORDER BY created_at, filename`,
    [applicationId],
  )
  return rows.map(({ fields, confidence, ...d }) => ({ ...d, facts: facts({ ...d, fields }), low_fields: confidence?.low || [] }))
}

/** Spend and time across every task run for the application and its documents (retries included). */
async function usageTotals(applicationId) {
  return db.one(
    `SELECT coalesce(sum(cost_usd), 0) AS cost_usd, coalesce(sum(duration_s), 0) AS processing_s, count(*) AS runs,
            coalesce(sum(ocr_pages), 0) AS ocr_pages, coalesce(sum(calls), 0) AS llm_calls
       FROM usage_log
      WHERE ref_id = $1 OR ref_id IN (SELECT id FROM documents WHERE application_id = $1)`,
    [applicationId],
  )
}

async function pendingCount(applicationId) {
  const row = await db.one('SELECT count(*) AS n FROM documents WHERE application_id = $1 AND status = ANY($2)', [applicationId, ACTIVE])
  return row.n
}

/**
 * Check, store and queue uploaded files for an application. Files are written before their rows exist,
 * so the worker never sees a document without its file.
 */
async function addDocuments(app, files) {
  if (!files.length) throw new HttpError(400, 'Upload at least one file in the "files" field')
  const { n: existing } = await db.one('SELECT count(*) AS n FROM documents WHERE application_id = $1', [app.id])
  if (existing + files.length > MAX_DOCUMENTS_PER_APPLICATION) {
    throw new HttpError(400, `An application can have at most ${MAX_DOCUMENTS_PER_APPLICATION} documents`)
  }

  const prepared = []
  for (const file of files) {
    const pages = await checkFile(file)
    const id = crypto.randomUUID()
    const key = storage.keyFor('uploads', app.id, `${id.slice(0, 8)}_${safeName(file.originalname)}`)
    prepared.push({ id, key, pages, file })
  }
  for (const p of prepared) await storage.put(p.key, p.file.buffer)

  await db.tx(async client => {
    for (const { id, key, pages, file } of prepared) {
      await client.query(
        'INSERT INTO documents (id, application_id, filename, storage_key, mime, size_bytes, pages) VALUES ($1, $2, $3, $4, $5, $6, $7)',
        [id, app.id, file.originalname, key, FILE_TYPES[extOf(file.originalname)], file.size ?? file.buffer.length, pages],
      )
    }
    await client.query(
      `UPDATE applications SET status = 'processing', error = '', progress = '{"stage": "queued"}', approved_at = NULL, updated_at = now() WHERE id = $1`,
      [app.id],
    )
  })
  await queueDocuments(app.id, prepared.map(p => p.id))
  return prepared.map(p => p.id)
}

async function removeApplication(id) {
  await storage.removeFolder(storage.keyFor('uploads', id))
  await db.pool.query('DELETE FROM applications WHERE id = $1', [id])
}

module.exports = { ACTIVE, findApplication, listDocuments, usageTotals, pendingCount, addDocuments, removeApplication }
