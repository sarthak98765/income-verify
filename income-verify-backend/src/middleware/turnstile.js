const { TURNSTILE_SECRET_KEY } = require('../config')

// Cloudflare Turnstile on the routes that start paid OCR and model work. The browser sends a one-time token in the
// `cf-turnstile-response` header; it is checked with Cloudflare before the route runs. With no secret key set
// (local development) the check is skipped.

const VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

async function verify(token, ip, secret = TURNSTILE_SECRET_KEY) {
  const body = new URLSearchParams({ secret, response: token })
  if (ip) body.set('remoteip', ip)
  const res = await fetch(VERIFY_URL, { method: 'POST', body, signal: AbortSignal.timeout(8000) })
  const data = await res.json()
  return data.success === true
}

function turnstile(secret = TURNSTILE_SECRET_KEY, check = verify) {
  return async (req, res, next) => {
    if (!secret) return next()
    const token = req.get('cf-turnstile-response')
    if (!token) return res.status(403).json({ message: 'Confirm you are not a bot, then try again.' })
    try {
      if (await check(token, req.ip, secret)) return next()
      return res.status(403).json({ message: 'The bot check failed or expired. Try again.' })
    } catch (err) {
      console.error('[turnstile] could not reach Cloudflare:', err.message)
      return res.status(503).json({ message: 'The bot check is unavailable right now. Try again in a minute.' })
    }
  }
}

module.exports = { turnstile, verify, humanCheck: turnstile() }
