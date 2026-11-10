// Pipeline load test: N applicants uploaded at the same moment through the real path (create → upload → queue →
// worker → verdict), and how long each waits for its verdict. Uses fresh synthetic files (never read before), so
// OCR is not served from cache.
//
//   python -m data_gen.generate --split load --count 16 --seed 4      # in income-verify-ml, once
//   node loadtest/pipeline.mjs 1 5 10                                 # batch sizes, run one after another
//
// Each batch takes the next unused applicants from data/load. Applications are deleted afterwards.
import fs from 'node:fs'
import path from 'node:path'

const BASE = process.env.BASE_URL || 'http://localhost:5920'
const DATA = path.resolve(import.meta.dirname, '../income-verify-ml/data/load')
const OUT = path.resolve(import.meta.dirname, 'results/pipeline.json')
const POLL_MS = 3000
const TYPES = { pdf: 'application/pdf', jpg: 'image/jpeg', png: 'image/png' }

const sizes = process.argv.slice(2).map(Number).filter(Boolean)
const folders = fs.readdirSync(DATA).filter(f => fs.existsSync(path.join(DATA, f, 'truth.json'))).sort()
const sleep = ms => new Promise(r => setTimeout(r, ms))

async function api(method, url, body) {
  const res = await fetch(BASE + url, { method, body, headers: body && !(body instanceof FormData) ? { 'content-type': 'application/json' } : undefined })
  if (!res.ok) throw new Error(`${method} ${url}: ${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

async function submit(folder) {
  const truth = JSON.parse(fs.readFileSync(path.join(DATA, folder, 'truth.json')))
  const app = truth.application || {}
  const created = await api('POST', '/applications', JSON.stringify({
    applicant_name: app.applicant_name, declared_employer: app.declared_employer, declared_monthly_income: app.declared_monthly_income,
  }))
  const form = new FormData()
  for (const f of truth.documents.map(d => d.file)) {
    const bytes = fs.readFileSync(path.join(DATA, folder, f))
    form.append('files', new Blob([bytes], { type: TYPES[f.split('.').pop()] }), f)
  }
  await api('POST', `/applications/${created.id}/documents`, form)
  return { folder, id: created.id, expected: truth.expected_status, submitted: Date.now() }
}

async function waitAll(jobs) {
  const open = new Set(jobs)
  while (open.size) {
    await sleep(POLL_MS)
    // one list call per cycle (the per-IP rate limit is 600 requests per 15 min); the detail only once, when done
    const byId = new Map((await api('GET', '/applications?limit=200')).map(a => [a.id, a]))
    for (const job of [...open]) {
      const a = byId.get(job.id)
      if (a && a.status !== 'processing' && a.status !== 'draft' && a.analyzed_at) {
        const detail = await api('GET', `/applications/${job.id}`)
        Object.assign(job, { done: Date.now(), status: a.status, cost: detail.totals?.cost_usd, ocr_pages: detail.totals?.ocr_pages })
        open.delete(job)
      }
    }
  }
}

const pct = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)] }

const results = []
let next = 0
for (const n of sizes) {
  if (next + n > folders.length) throw new Error(`Need ${next + n} applicants in data/load, have ${folders.length}`)
  const batch = folders.slice(next, next + n)
  next += n
  console.log(`\n▶ ${n} at once: ${batch.join(', ')}`)
  const t0 = Date.now()
  const jobs = await Promise.all(batch.map(submit))
  await waitAll(jobs)
  const waits = jobs.map(j => (j.done - j.submitted) / 1000)
  const makespan = (Math.max(...jobs.map(j => j.done)) - t0) / 1000
  const row = {
    concurrent: n, p50_s: Math.round(pct(waits, 0.5)), p95_s: Math.round(pct(waits, 0.95)), makespan_s: Math.round(makespan),
    per_hour: Math.round((n / makespan) * 3600), verdicts_right: jobs.filter(j => j.status === j.expected).length,
    cost_usd: Number(jobs.reduce((s, j) => s + (j.cost || 0), 0).toFixed(3)), ocr_pages: jobs.reduce((s, j) => s + (j.ocr_pages || 0), 0),
  }
  results.push(row)
  console.log(row)
  await Promise.all(jobs.map(j => api('DELETE', `/applications/${j.id}`)))
}

fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify({ base: BASE, at: new Date().toISOString(), results }, null, 1))
console.log(`\n→ ${OUT}`)
