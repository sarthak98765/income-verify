const express = require('express')
const db = require('../db')
const storage = require('../storage')
const { applyEdits } = require('../fields')
const { queueAnalysis } = require('../jobs')
const { pendingCount } = require('../applications')
const { parse, parseId } = require('../validate')
const { wrap, HttpError } = require('../middleware/error')

const router = express.Router()

async function findDocument(id) {
  const doc = await db.one('SELECT * FROM documents WHERE id = $1', [parseId(id)])
  if (!doc) throw new HttpError(404, 'Document not found')
  return doc
}

// Extracted fields, confidence and checks for the review screen. The model's raw output stays server-side.
router.get('/:id', wrap(async (req, res) => {
  const { raw, storage_key, ...doc } = await findDocument(req.params.id)
  const [application, edits, siblings] = await Promise.all([
    db.one('SELECT id, applicant_name, status FROM applications WHERE id = $1', [doc.application_id]),
    db.all('SELECT field_path, old_value, new_value, edited_by, created_at FROM field_edits WHERE document_id = $1 ORDER BY created_at', [doc.id]),
    db.all('SELECT id, filename, doc_type, status FROM documents WHERE application_id = $1 ORDER BY created_at, filename', [doc.application_id]),
  ])
  res.json({ ...doc, application, edits, siblings })
}))

// The original upload, for the viewer beside the fields.
router.get('/:id/file', wrap(async (req, res) => {
  const doc = await findDocument(req.params.id)
  const file = await storage.stat(doc.storage_key)
  if (!file) throw new HttpError(404, 'The file is no longer stored')
  res.setHeader('Content-Type', doc.mime)
  res.setHeader('Content-Length', file.length)
  res.setHeader('Content-Disposition', `inline; filename="${doc.filename.replace(/[^\w.-]+/g, '_')}"`)
  res.setHeader('Cache-Control', 'private, max-age=3600')
  storage.openReadStream(doc.storage_key).on('error', () => res.destroy()).pipe(res)
}))

// A reviewer's corrections. Each change is audited in field_edits, then the whole application is
// analysed again: the worker re-runs the checks on the corrected fields and recomputes the verdict.
router.patch('/:id/fields', wrap(async (req, res) => {
  const { edits } = parse('fieldEdits', req.body)
  const doc = await findDocument(req.params.id)
  if (doc.status !== 'completed') throw new HttpError(409, 'Only a document that has been read can be edited')
  const app = await db.one('SELECT id, status FROM applications WHERE id = $1', [doc.application_id])
  if (app.status === 'approved') throw new HttpError(409, 'This application is approved; its fields can no longer change')
  if (await pendingCount(app.id)) throw new HttpError(409, 'Other documents are still being read; try again when they finish')

  const { fields, changes } = applyEdits(doc.fields, edits)
  if (!changes.length) return res.json({ changed: 0, document_id: doc.id })

  await db.tx(async client => {
    await client.query('UPDATE documents SET fields = $2, updated_at = now() WHERE id = $1', [doc.id, JSON.stringify(fields)])
    for (const c of changes) {
      await client.query('INSERT INTO field_edits (document_id, field_path, old_value, new_value) VALUES ($1, $2, $3, $4)',
        [doc.id, c.path, JSON.stringify(c.old), JSON.stringify(c.new)])
    }
    await client.query(`UPDATE applications SET status = 'processing', error = '', progress = '{"stage": "queued"}', updated_at = now() WHERE id = $1`, [app.id])
  })
  await queueAnalysis(app.id)
  res.json({ changed: changes.length, document_id: doc.id, changes })
}))

module.exports = router
