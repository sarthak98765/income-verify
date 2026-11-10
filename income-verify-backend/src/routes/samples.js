const express = require('express')
const db = require('../db')
const { uploadLimiter } = require('../limits')
const { humanCheck } = require('../middleware/turnstile')
const { listSamples, loadSample } = require('../samples')
const { addDocuments, findApplication, listDocuments } = require('../applications')
const { wrap, HttpError } = require('../middleware/error')

const router = express.Router()

router.get('/', wrap(async (_req, res) => {
  res.json(listSamples())
}))

// Create an application from a bundled synthetic applicant and queue its documents, like a real upload.
router.post('/:key', uploadLimiter, humanCheck, wrap(async (req, res) => {
  const sample = loadSample(req.params.key)
  if (!sample) throw new HttpError(404, 'No such sample applicant')
  const { applicant_name, declared_employer, declared_monthly_income } = sample.application
  const app = await db.one(
    'INSERT INTO applications (applicant_name, declared_employer, declared_monthly_income, is_sample) VALUES ($1, $2, $3, true) RETURNING *',
    [applicant_name, declared_employer || '', declared_monthly_income ?? null],
  )
  await addDocuments(app, sample.files)
  res.status(201).json({ ...(await findApplication(app.id)), documents: await listDocuments(app.id) })
}))

module.exports = router
