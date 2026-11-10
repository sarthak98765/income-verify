const { rateLimit } = require('express-rate-limit')
const { RATE_LIMIT, UPLOAD_RATE_LIMIT } = require('./config')

// Per-IP limits. The upload limiter guards the routes that start paid OCR and model work.
const limiter = ({ windowMinutes, max }, message) => rateLimit({
  windowMs: windowMinutes * 60 * 1000,
  limit: max,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  message: { message },
})

module.exports = {
  apiLimiter: limiter(RATE_LIMIT, 'Too many requests. Please wait a few minutes and try again.'),
  uploadLimiter: limiter(UPLOAD_RATE_LIMIT, 'Upload limit reached for this hour. Please try again later.'),
}
