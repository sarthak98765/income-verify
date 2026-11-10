// k6 load test for the read endpoints the UI polls: the applications list, an application, a document, stats.
//
//   k6 run loadtest/api.js                       # against a backend started with TRUST_PROXY=1 (see results.md)
//   BASE_URL=http://localhost:5940 k6 run loadtest/api.js
//   STRESS=1 k6 run loadtest/api.js              # 100 users with no pause for 60 s: the ceiling, not normal use
//
// Each virtual user sends its own X-Forwarded-For, the way real visitors arrive through the proxy, so the per-IP
// rate limiter treats them as separate people (one machine would otherwise be throttled after 600 requests).
// Uploads are not here: they start paid OCR and model work, and are measured by pipeline.mjs instead.
import http from 'k6/http'
import { check, sleep } from 'k6'

const BASE = __ENV.BASE_URL || 'http://localhost:5940'
const PEAK = Number(__ENV.PEAK_VUS || 50)
const STRESS = Boolean(__ENV.STRESS)

export const options = {
  scenarios: STRESS ? { stress: { executor: 'constant-vus', vus: 100, duration: '60s' } } : {
    browse: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '45s', target: PEAK / 2 },
        { duration: '45s', target: PEAK },
        { duration: '90s', target: PEAK },
        { duration: '20s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{name:list}': ['p(95)<500'],
    'http_req_duration{name:application}': ['p(95)<500'],
    'http_req_duration{name:document}': ['p(95)<800'],
    'http_req_duration{name:stats}': ['p(95)<500'],
  },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
}

export function setup() {
  const apps = http.get(`${BASE}/applications`).json()
  const appIds = apps.map(a => a.id)
  const docIds = []
  for (const id of appIds.slice(0, 5)) {
    for (const d of http.get(`${BASE}/applications/${id}`).json().documents) docIds.push(d.id)
  }
  if (!appIds.length || !docIds.length) throw new Error('Run a sample applicant first, so there is something to read.')
  return { appIds, docIds }
}

const pick = list => list[Math.floor(Math.random() * list.length)]

export default function (data) {
  // In stress mode a user's address changes every 500 requests, so the rate limiter (600 per 15 min) isn't what's measured.
  const client = STRESS ? __VU * 4096 + Math.floor(__ITER / 500) : __VU
  const params = name => ({ headers: { 'X-Forwarded-For': `10.${(client >> 16) & 255}.${(client >> 8) & 255}.${client & 255}` }, tags: { name } })
  const r = Math.random()
  let res
  if (r < 0.4) res = http.get(`${BASE}/applications`, params('list'))
  else if (r < 0.75) res = http.get(`${BASE}/applications/${pick(data.appIds)}`, params('application'))
  else if (r < 0.9) res = http.get(`${BASE}/documents/${pick(data.docIds)}`, params('document'))
  else res = http.get(`${BASE}/stats`, params('stats'))
  check(res, { 'status 200': x => x.status === 200 })
  if (!STRESS) sleep(1 + Math.random()) // a person polling a page every 1-2 s
}

export function handleSummary(data) {
  return { [`loadtest/results/api-${STRESS ? 'stress' : 'browse'}.json`]: JSON.stringify(data, null, 1) }
}
