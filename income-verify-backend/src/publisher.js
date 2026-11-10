const amqp = require('amqplib')
const { RABBITMQ_URL, RABBITMQ_EXCHANGE, RABBITMQ_MAIN_QUEUE } = require('./config')

let _conn = null
let _channel = null

async function getChannel() {
  if (_channel) return _channel
  _conn = await amqp.connect(RABBITMQ_URL)
  _channel = await _conn.createConfirmChannel()
  // The exchange and queues come from infra/rabbitmq/definitions.json at broker boot; assert nothing.
  await _channel.checkExchange(RABBITMQ_EXCHANGE)

  const reset = () => { _conn = null; _channel = null }
  _conn.on('error', reset)
  _conn.on('close', reset)
  return _channel
}

// The message carries only a task and a row id; every parameter lives on the row, so redelivery is safe.
//   process_document     id = documents.id      OCR → classify → extract → checks → signals
//   analyze_application  id = applications.id   cross-checks → metrics → verdict → summary
async function publishJob(task, id) {
  const channel = await getChannel()
  channel.publish(RABBITMQ_EXCHANGE, RABBITMQ_MAIN_QUEUE, Buffer.from(JSON.stringify({ task, id })), { persistent: true, contentType: 'application/json' })
  await channel.waitForConfirms()
}

async function close() {
  if (_conn) await _conn.close().catch(() => {})
}

module.exports = { publishJob, close }
