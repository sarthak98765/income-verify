const express = require('express')
const db = require('../db')
const { upload } = require('../upload')
const { uploadLimiter } = require('../limits')
const { humanCheck } = require('../middleware/turnstile')
const { queueAnalysis } = require('../jobs')
const { buildJson, buildXlsx } = require('../export')
const { findApplication, listDocuments, usageTotals, pendingCount, addDocuments, removeApplication } = require('../applications')
const { parse, parseId } = require('../validate')
const { wrap, HttpError } = require('../middleware/error')

const router = express.Router()

const ANALYSED = ['verified', 'needs_review', 'flagged']

// The list needs status, headline numbers and the reasons (for the top one), not the rest of the JSONB detail.
const LIST_COLUMNS = `a.id, a.applicant_name, a.declared_employer, a.declared_monthly_income, a.status, a.authenticity_score,
  a.verified_monthly_income, a.foir, a.reasons, a.progress, a.is_sample, a.error, a.approved_at, a.analyzed_at, a.created_at, a.updated_at`

router.post('/', humanCheck, wrap(async (req, res) => {
  const body = parse('createApplication', req.body)
  const app = await db.one(
    'INSERT INTO applications (applicant_name, declared_employer, declared_monthly_income) VALUES ($1, $2, $3) RETURNING *',
    [body.applicant_name, body.declared_employer, body.declared_monthly_income],
  )
  res.status(201).json(app)
}))

// Newest first, with document counts and spend so the list can show progress and cost per row.
router.get('/', wrap(async (req, res) => {
  const { status, q, limit } = parse('listApplications', req.query)
  const rows = await db.all(
    `SELECT ${LIST_COLUMNS},
            (SELECT count(*) FROM documents d WHERE d.application_id = a.id) AS documents_count,
            (SELECT count(*) FROM documents d WHERE d.application_id = a.id AND d.status = 'completed') AS documents_done,
            (SELECT count(*) FROM documents d WHERE d.application_id = a.id AND d.status = 'failed') AS documents_failed
       FROM applications a
      WHERE ($1::text IS NULL OR a.status = $1) AND ($2::text IS NULL OR a.applicant_name ILIKE '%' || $2 || '%')
      ORDER BY a.created_at DESC LIMIT $3`,
    [status ?? null, q || null, limit],
  )
  res.json(rows)
}))

router.get('/:id', wrap(async (req, res) => {
  const app = await findApplication(parseId(req.params.id))
  const [documents, usage, edits] = await Promise.all([
    listDocuments(app.id),
    usageTotals(app.id),
    db.one('SELECT count(*) AS n FROM field_edits e JOIN documents d ON d.id = e.document_id WHERE d.application_id = $1', [app.id]),
  ])
  res.json({ ...app, documents, totals: usage, edits_count: edits.n })
}))

router.post('/:id/documents', uploadLimiter, humanCheck, upload.array('files'), wrap(async (req, res) => {
  const app = await findApplication(parseId(req.params.id))
  if (app.status === 'approved') throw new HttpError(409, 'This application is approved; documents can no longer be added')
  const ids = await addDocuments(app, req.files || [])
  res.status(201).json({ ...(await findApplication(app.id)), documents: await listDocuments(app.id), added: ids })
}))

// Run the analysis again, e.g. after it failed. Documents still being read must finish first.
router.post('/:id/analyze', wrap(async (req, res) => {
  const app = await findApplication(parseId(req.params.id))
  if (app.status === 'approved') throw new HttpError(409, 'This application is already approved')
  if (await pendingCount(app.id)) throw new HttpError(409, 'Documents are still being read')
  await db.pool.query(`UPDATE applications SET status = 'processing', error = '', progress = '{"stage": "queued"}', updated_at = now() WHERE id = $1`, [app.id])
  await queueAnalysis(app.id)
  res.json(await findApplication(app.id))
}))

// Final sign-off by the reviewer. Only an analysed application can be approved.
router.post('/:id/approve', wrap(async (req, res) => {
  const app = await findApplication(parseId(req.params.id))
  if (!ANALYSED.includes(app.status)) throw new HttpError(409, app.status === 'approved' ? 'Already approved' : 'Only an analysed application can be approved')
  if (await pendingCount(app.id)) throw new HttpError(409, 'Documents are still being read')
  res.json(await db.one("UPDATE applications SET status = 'approved', approved_at = now(), updated_at = now() WHERE id = $1 RETURNING *", [app.id]))
}))

router.get('/:id/export', wrap(async (req, res) => {
  const { format } = parse('exportQuery', req.query)
  const app = await findApplication(parseId(req.params.id))
  const documents = await db.all("SELECT * FROM documents WHERE application_id = $1 AND status = 'completed' ORDER BY created_at, filename", [app.id])
  const edits = await db.all(
    `SELECT d.filename, e.field_path, e.old_value, e.new_value, e.edited_by, e.created_at
       FROM field_edits e JOIN documents d ON d.id = e.document_id WHERE d.application_id = $1 ORDER BY e.created_at`,
    [app.id],
  )
  const base = `income-verify-${app.applicant_name.replace(/[^\w-]+/g, '_')}-${app.id.slice(0, 8)}`
  if (format === 'xlsx') {
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    res.setHeader('Content-Disposition', `attachment; filename="${base}.xlsx"`)
    return res.send(await buildXlsx(app, documents, edits))
  }
  res.setHeader('Content-Disposition', `attachment; filename="${base}.json"`)
  res.json(buildJson(app, documents, edits))
}))

router.delete('/:id', wrap(async (req, res) => {
  const app = await findApplication(parseId(req.params.id))
  await removeApplication(app.id)
  res.json({ deleted: true })
}))

module.exports = router
