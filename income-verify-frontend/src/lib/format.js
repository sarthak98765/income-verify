// Indian grouping: 1,23,456. Whole rupees by default; paise where the document prints them.
const INR0 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const INR2 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const NUM2 = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const rupees = (n, paise = false) => (n == null || Number.isNaN(Number(n)) ? '–' : (paise ? INR2 : INR0).format(Number(n)))
export const amount = n => (n == null ? '' : NUM2.format(Number(n)))
export const pct = (fraction, digits = 0) => (fraction == null ? '–' : `${(Number(fraction) * 100).toFixed(digits)}%`)
export const usd = n => (n == null ? '–' : `$${Number(n) < 0.01 && Number(n) > 0 ? Number(n).toFixed(4) : Number(n).toFixed(3)}`)
export const seconds = s => (s == null ? '–' : s < 90 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`)
export const fmtSize = bytes => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`)

export const fmtDate = d => (d ? new Date(d).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '')
export const fmtDay = d => (d ? new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '–')

// "2026-07" → "Jul 2026"
export const fmtMonth = m => {
  if (!m || !/^\d{4}-\d{2}$/.test(m)) return m || '–'
  return new Date(`${m}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
}

export function timeAgo(d) {
  if (!d) return ''
  const s = Math.max(0, (Date.now() - new Date(d).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return fmtDay(d)
}

export const DOC_TYPES = {
  payslip: 'Payslip',
  bank_statement: 'Bank statement',
  form16: 'Form 16',
  unknown: 'Unrecognised',
}

// "salary_credit" → "Salary credit"
export const humanize = key => (key || '').replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())

// PAN and account numbers are shown with only the last 4 characters: "UDFPB4158N" → "••••••158N".
export const mask = v => {
  const s = v == null ? '' : String(v)
  return s.length <= 4 ? s : `${'•'.repeat(s.length - 4)}${s.slice(-4)}`
}
