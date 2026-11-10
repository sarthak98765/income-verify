const cors = require('cors')
const express = require('express')

const config = require('./config')
const db = require('./db')
const publisher = require('./publisher')
const { apiLimiter } = require('./limits')
const { startCleanup } = require('./cleanup')
const { notFound, errorHandler } = require('./middleware/error')

const app = express()
app.set('trust proxy', config.TRUST_PROXY)
app.disable('x-powered-by')

app.use(cors({ origin: config.CORS_ORIGINS.length ? config.CORS_ORIGINS : true }))
app.use(express.json({ limit: '1mb' }))

app.get('/health', (_req, res) => res.json({ status: 'OK' }))

app.use(apiLimiter)
app.use('/applications', require('./routes/applications'))
app.use('/documents', require('./routes/documents'))
app.use('/samples', require('./routes/samples'))
app.use('/stats', require('./routes/stats'))

app.use(notFound)
app.use(errorHandler)

async function start() {
  await db.connect()
  startCleanup()
  const server = app.listen(config.APP_PORT, () => {
    console.log(`[api] listening on :${config.APP_PORT} (${config.NODE_ENV}) storage=${config.STORAGE_DIR}`)
  })

  const shutdown = signal => {
    console.log(`[api] ${signal} received, shutting down`)
    server.close(async () => {
      await publisher.close()
      await db.pool.end()
      process.exit(0)
    })
    setTimeout(() => process.exit(1), 10_000).unref()
  }
  process.on('SIGTERM', () => shutdown('SIGTERM'))
  process.on('SIGINT', () => shutdown('SIGINT'))
}

if (require.main === module) {
  start().catch(err => {
    console.error('[api] failed to start:', err)
    process.exit(1)
  })
}

module.exports = app
