const assert = require('node:assert/strict')
const { describe, it } = require('node:test')
const { turnstile } = require('../src/middleware/turnstile')

// Offline: the Cloudflare call is replaced by a stub.
function run(middleware, token) {
  return new Promise(resolve => {
    const req = { ip: '1.2.3.4', get: name => (name === 'cf-turnstile-response' ? token : undefined) }
    const res = { status(code) { this.code = code; return this }, json(body) { resolve({ code: this.code, body }) } }
    middleware(req, res, () => resolve({ code: 'next' }))
  })
}

describe('turnstile bot check', () => {
  it('is skipped when no secret is configured', async () => {
    assert.equal((await run(turnstile(''), undefined)).code, 'next')
  })

  it('rejects a request without a token', async () => {
    assert.equal((await run(turnstile('secret', async () => true), undefined)).code, 403)
  })

  it('lets a verified token through and stops a bad one', async () => {
    const check = async token => token === 'good'
    assert.equal((await run(turnstile('secret', check), 'good')).code, 'next')
    assert.equal((await run(turnstile('secret', check), 'bad')).code, 403)
  })

  it('answers 503 when Cloudflare cannot be reached', async () => {
    const down = async () => { throw new Error('timeout') }
    assert.equal((await run(turnstile('secret', down), 'good')).code, 503)
  })
})
