const db = require('./db')
const { removeApplication } = require('./applications')
const { RETENTION_HOURS, CLEANUP_EVERY_MINUTES } = require('./config')

// Public demo hygiene: applications older than RETENTION_HOURS are deleted with their files.
// Rows go via ON DELETE CASCADE (documents, field_edits); usage_log is kept for the cost numbers.
async function sweep() {
  const old = await db.all(`SELECT id FROM applications WHERE created_at < now() - make_interval(hours => $1) AND status <> 'processing'`, [RETENTION_HOURS])
  for (const { id } of old) {
    try {
      await removeApplication(id)
    } catch (err) {
      console.error(`[cleanup] could not delete application ${id}:`, err.message)
    }
  }
  if (old.length) console.log(`[cleanup] deleted ${old.length} application(s) older than ${RETENTION_HOURS}h`)
}

function startCleanup() {
  if (!RETENTION_HOURS) return null
  const run = () => sweep().catch(err => console.error('[cleanup] sweep failed:', err.message))
  run()
  return setInterval(run, CLEANUP_EVERY_MINUTES * 60 * 1000).unref()
}

module.exports = { startCleanup, sweep }
