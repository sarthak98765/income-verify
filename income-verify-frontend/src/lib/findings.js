import { DOC_TYPES, fmtMonth, humanize } from '@/lib/format'

// Turns an application's reasons into findings a reviewer can act on: deduplicated, weighted by the
// fraud signal behind them, linked to the document and page they came from, and with the
// "Low confidence: <type>: <path>" lines grouped into one plain sentence per document.

export function docLabel(d) {
  if (!d) return ''
  const type = DOC_TYPES[d.doc_type] || d.filename
  return d.doc_type === 'payslip' && d.facts?.month ? `${type}, ${fmtMonth(d.facts.month)}` : type
}

const stripType = m => m.replace(/^(payslip|bank_statement|form16): /, '')

const pathLabel = path => {
  const row = path.match(/^transactions\.(\d+)/)
  if (row) return `row ${Number(row[1]) + 1}`
  return humanize(path.split('.').pop())
}

const joinList = items => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`)

export function buildFindings(app) {
  const docs = app.documents || []
  // message (without the "payslip: " prefix) → where it came from
  const source = new Map()
  for (const d of docs) {
    for (const s of d.signals || []) source.set(stripType(s.message), { doc: d, page: s.page })
    for (const c of d.checks || []) if (c.status !== 'pass') source.set(stripType(c.message), { doc: d, page: c.page, focus: c.fields?.[0] })
  }
  const weight = new Map((app.signals || []).map(s => [stripType(s.message), s.weight]))
  const pageOf = new Map((app.signals || []).map(s => [stripType(s.message), s.page]))

  const low = new Map() // doc type → [paths]
  const out = []
  const seen = new Set()
  for (const reason of app.reasons || []) {
    const lowMatch = reason.match(/^Low confidence: (\w+): (.+)$/)
    if (lowMatch) {
      const [, type, path] = lowMatch
      low.set(type, [...(low.get(type) || []), path])
      continue
    }
    const key = stripType(reason)
    if (seen.has(key)) continue
    seen.add(key)
    const src = source.get(key)
    const salaryMonth = key.match(/^(\d{4}-\d{2}):/)?.[1]
    const doc = src?.doc || (salaryMonth ? docs.find(d => d.doc_type === 'bank_statement') : null)
    out.push({ text: key, weight: weight.get(key) ?? null, doc, page: src?.page ?? pageOf.get(key) ?? null, focus: src?.focus })
  }
  for (const [type, paths] of low) {
    const doc = docs.find(d => d.doc_type === type && (d.low_fields || []).some(p => paths.includes(p))) || docs.find(d => d.doc_type === type)
    const labels = [...new Set(paths.map(pathLabel))]
    out.push({ text: `Values to confirm by eye: ${joinList(labels.slice(0, 6))}${labels.length > 6 ? ` and ${labels.length - 6} more` : ''}`, weight: null, doc, page: null, focus: paths[0], confirm: true })
  }
  return out.sort((a, b) => (b.weight ?? -1) - (a.weight ?? -1))
}

export function verdictSentence(app, findings) {
  const n = findings.filter(f => !f.confirm).length
  if (app.status === 'verified') return 'Every check passed and nothing suggests a document was changed.'
  if (app.status === 'needs_review') return `Nothing looks forged, but ${n === 1 ? 'one thing needs' : `${n || 'some'} things need`} a person to look before approving.`
  if (app.status === 'flagged') return `${n === 1 ? 'One sign' : `${n} signs`} that this file may have been changed. Check the originals before going further.`
  return ''
}

/** Link to the review screen, opened at the page and value a finding points to. */
export function reviewLink(doc, { page, focus } = {}) {
  const q = new URLSearchParams()
  if (focus) q.set('focus', focus)
  if (page) q.set('page', page)
  const qs = q.toString()
  return `/documents/${doc.id}${qs ? `?${qs}` : ''}`
}
