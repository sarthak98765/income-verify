const db = require('./db')
const { publishJob } = require('./publisher')

const BROKER_HINT = 'Is RabbitMQ running (docker compose up -d rabbitmq)?'

// If the broker is down, the row is marked failed with a reason the UI can show, instead of sitting queued forever.
async function queueDocument(documentId) {
  try {
    await publishJob('process_document', documentId)
    return true
  } catch (err) {
    console.error(`[jobs] publish process_document ${documentId} failed:`, err.message)
    await db.pool.query("UPDATE documents SET status = 'failed', error = $2, updated_at = now() WHERE id = $1", [documentId, `Could not queue the document: ${err.message}. ${BROKER_HINT}`])
    return false
  }
}

async function queueDocuments(applicationId, documentIds) {
  let queued = 0
  for (const id of documentIds) queued += await queueDocument(id) ? 1 : 0
  if (!queued) await markApplicationFailed(applicationId, `Could not queue any document. ${BROKER_HINT}`)
  return queued
}

async function queueAnalysis(applicationId) {
  try {
    await publishJob('analyze_application', applicationId)
    return true
  } catch (err) {
    console.error(`[jobs] publish analyze_application ${applicationId} failed:`, err.message)
    await markApplicationFailed(applicationId, `Could not queue the analysis: ${err.message}. ${BROKER_HINT}`)
    return false
  }
}

function markApplicationFailed(applicationId, error) {
  return db.pool.query("UPDATE applications SET status = 'failed', error = $2, updated_at = now() WHERE id = $1", [applicationId, error])
}

module.exports = { queueDocuments, queueAnalysis }
