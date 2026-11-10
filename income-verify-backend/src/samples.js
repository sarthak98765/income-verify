const fs = require('fs')
const path = require('path')
const { SAMPLES_DIR, ISSUE_LABELS } = require('./config')

/**
 * Synthetic applicants from income-verify-ml/data_gen (manifest.json + one folder per applicant with
 * its files and truth.json). Every file carries a "SYNTHETIC SPECIMEN" footer; no real person's data.
 */

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

/** The sample picker's list. Empty when the samples have not been generated. */
function listSamples() {
  const manifest = path.join(SAMPLES_DIR, 'manifest.json')
  if (!fs.existsSync(manifest)) return []
  return readJson(manifest).map(entry => {
    const truth = readJson(path.join(SAMPLES_DIR, entry.id, 'truth.json'))
    return {
      key: entry.id,
      issue: entry.issue,
      label: ISSUE_LABELS[entry.issue] || entry.issue,
      expected: truth.expected_status,
      applicant_name: truth.application.applicant_name,
      declared_employer: truth.application.declared_employer,
      files: entry.files,
    }
  })
}

/** One sample's application fields and file buffers, or null for an unknown key. */
function loadSample(key) {
  const sample = listSamples().find(s => s.key === key)
  if (!sample) return null
  const truth = readJson(path.join(SAMPLES_DIR, key, 'truth.json'))
  const files = sample.files.map(name => {
    const buffer = fs.readFileSync(path.join(SAMPLES_DIR, key, name))
    return { originalname: name, buffer, size: buffer.length }
  })
  return { application: truth.application, files }
}

module.exports = { listSamples, loadSample }
