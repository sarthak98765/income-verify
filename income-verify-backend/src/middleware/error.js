const multer = require('multer')
const { NODE_ENV, MAX_FILE_MB, MAX_FILES_PER_UPLOAD } = require('../config')

function notFound(req, res) {
  res.status(404).json({ message: `No route for ${req.method} ${req.path}` })
}

const MULTER_MESSAGES = {
  LIMIT_FILE_SIZE: `A file is larger than ${MAX_FILE_MB} MB`,
  LIMIT_FILE_COUNT: `Upload at most ${MAX_FILES_PER_UPLOAD} files at a time`,
  LIMIT_UNEXPECTED_FILE: 'Send the files in the "files" field',
}

// One JSON error shape for everything, so nothing surfaces as an HTML stack trace.
function errorHandler(err, _req, res, _next) {
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ message: MULTER_MESSAGES[err.code] || `Upload failed: ${err.message}` })
  }
  // Malformed JSON body, or a bad uuid reaching Postgres.
  if (err?.type === 'entity.parse.failed') return res.status(400).json({ message: 'Request body is not valid JSON' })
  if (err?.code === '22P02') return res.status(404).json({ message: 'Not found' })

  const status = err.status || err.statusCode || 500
  if (status >= 500) console.error('[error]', err)
  res.status(status).json({
    message: status >= 500 && NODE_ENV === 'production' ? 'Something went wrong' : err.message || 'Something went wrong',
  })
}

// Express 4 does not catch a rejected promise from an async handler; this sends it to errorHandler.
const wrap = fn => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next)

// Throw for expected failures; errorHandler turns it into a clean response.
class HttpError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

module.exports = { notFound, errorHandler, wrap, HttpError }
