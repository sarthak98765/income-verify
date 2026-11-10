// Cloudflare Turnstile: a fresh one-time token just before a request that starts paid work. One hidden widget
// for the whole app; it only shows itself if Cloudflare wants the visitor to click. No site key = off (local).

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''
const SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
const TIMEOUT_MS = 30000

let loading = null
let widgetId = null
let waiting = null

const loadScript = () => {
  loading ||= new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SCRIPT
    s.async = true
    s.onload = () => resolve(window.turnstile)
    s.onerror = () => { loading = null; reject(new Error('Could not load the bot check. Check your connection and try again.')) }
    document.head.appendChild(s)
  })
  return loading
}

function ensureWidget(ts) {
  if (widgetId != null) return
  const box = document.createElement('div')
  box.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:70'
  document.body.appendChild(box)
  widgetId = ts.render(box, {
    sitekey: SITE_KEY,
    execution: 'execute',
    appearance: 'interaction-only',
    callback: token => waiting?.resolve(token),
    'error-callback': () => waiting?.reject(new Error('The bot check failed. Try again.')),
    'timeout-callback': () => waiting?.reject(new Error('The bot check timed out. Try again.')),
  })
}

export const turnstileEnabled = () => Boolean(SITE_KEY)

/** A fresh token, or null when Turnstile is off. Tokens are single-use, so each request gets its own. */
export async function turnstileToken() {
  if (!SITE_KEY) return null
  const ts = await loadScript()
  ensureWidget(ts)
  const token = new Promise((resolve, reject) => {
    waiting = { resolve, reject }
    setTimeout(() => reject(new Error('The bot check took too long. Try again.')), TIMEOUT_MS)
  })
  ts.reset(widgetId)
  ts.execute(widgetId)
  return token
}
