const ExcelJS = require('exceljs')

/**
 * Export of one application: everything an underwriter or a loan system needs, nothing internal
 * (no raw model output, no progress). JSON for systems, xlsx for people.
 */

const APP_FIELDS = ['id', 'applicant_name', 'declared_employer', 'declared_monthly_income', 'status', 'authenticity_score', 'verified_monthly_income', 'foir',
  'metrics', 'salary_matches', 'cross_checks', 'signals', 'reasons', 'summary', 'approved_at', 'analyzed_at', 'created_at']
const DOC_FIELDS = ['id', 'filename', 'doc_type', 'pages', 'status', 'fields', 'checks', 'signals', 'confidence', 'error']

const pick = (row, keys) => Object.fromEntries(keys.map(k => [k, row[k]]))

function buildJson(app, documents, edits) {
  return {
    application: pick(app, APP_FIELDS),
    documents: documents.map(d => pick(d, DOC_FIELDS)),
    reviewer_edits: edits,
    generated_at: new Date().toISOString(),
  }
}

function sheet(book, name, columns, rows) {
  const ws = book.addWorksheet(name)
  ws.columns = columns.map(([header, key, width = 18, numFmt]) => ({ header, key, width, style: numFmt ? { numFmt } : {} }))
  ws.getRow(1).font = { bold: true }
  ws.views = [{ state: 'frozen', ySplit: 1 }]
  rows.forEach(r => ws.addRow(r))
  return ws
}

const INR = '#,##0.00'

/** Rows for the Checks sheet: the cross-document checks, then each document's own. */
function checkRows(app, documents) {
  const rows = (app.cross_checks || []).map(c => ({ source: 'Across documents', ...c }))
  for (const d of documents) for (const c of d.checks || []) rows.push({ source: d.filename, ...c })
  return rows
}

async function buildXlsx(app, documents, edits) {
  const book = new ExcelJS.Workbook()
  book.creator = 'IncomeVerify'
  const m = app.metrics || {}

  sheet(book, 'Summary', [['Item', 'item', 32], ['Value', 'value', 60]], [
    { item: 'Applicant', value: app.applicant_name },
    { item: 'Declared employer', value: app.declared_employer },
    { item: 'Declared monthly income', value: app.declared_monthly_income },
    { item: 'Verdict', value: app.status },
    { item: 'Authenticity score (0–100)', value: app.authenticity_score },
    { item: 'Verified monthly income', value: app.verified_monthly_income },
    { item: 'FOIR', value: app.foir },
    { item: 'Salary months matched', value: m.salary_months_checked != null ? `${m.salary_months_matched}/${m.salary_months_checked}` : null },
    { item: 'Average balance', value: m.average_balance },
    { item: 'Minimum balance', value: m.minimum_balance },
    { item: 'Existing EMIs per month', value: m.emi_total },
    { item: 'Bounces', value: (m.bounces || []).length },
    { item: 'Months of statement', value: m.months_covered },
    { item: 'Reasons', value: (app.reasons || []).join('\n') },
    { item: 'Underwriter note', value: app.summary },
    { item: 'Approved at', value: app.approved_at ? new Date(app.approved_at).toISOString() : '' },
  ]).getColumn('value').alignment = { wrapText: true, vertical: 'top' }

  sheet(book, 'Checks', [['Source', 'source', 28], ['Check', 'key', 24], ['Status', 'status', 10], ['Detail', 'message', 90], ['Page', 'page', 8]], checkRows(app, documents))

  const signals = [...(app.signals || [])]
  sheet(book, 'Fraud signals', [['Signal', 'key', 22], ['Weight', 'weight', 10], ['Detail', 'message', 90], ['Page', 'page', 8]], signals)

  sheet(book, 'Salary matches', [['Month', 'month', 12], ['Net pay', 'net_pay', 16, INR], ['Credited on', 'date', 14], ['Credit', 'amount', 16, INR], ['Narration', 'description', 60]],
    (app.salary_matches || []).map(s => ({ month: s.month, net_pay: s.net_pay, date: s.credit?.date || 'not found', amount: s.credit?.amount, description: s.credit?.description })))

  sheet(book, 'Payslips', [['File', 'file', 28], ['Month', 'month', 10], ['Employer', 'employer', 28], ['Employee', 'employee', 24], ['Gross', 'gross', 14, INR], ['Deductions', 'deductions', 14, INR], ['Net pay', 'net', 14, INR]],
    documents.filter(d => d.doc_type === 'payslip').map(d => ({ file: d.filename, month: d.fields.month, employer: d.fields.employer_name, employee: d.fields.employee_name, gross: d.fields.gross, deductions: d.fields.total_deductions, net: d.fields.net_pay })))

  const transactions = documents.filter(d => d.doc_type === 'bank_statement').flatMap(d => (d.fields.transactions || []).map(t => ({ file: d.filename, ...t })))
  sheet(book, 'Transactions', [['File', 'file', 22], ['Date', 'date', 12], ['Narration', 'description', 50], ['Debit', 'debit', 14, INR], ['Credit', 'credit', 14, INR], ['Balance', 'balance', 16, INR], ['Category', 'category', 14], ['Page', 'page', 6]], transactions)

  sheet(book, 'Reviewer edits', [['File', 'filename', 28], ['Field', 'field_path', 30], ['Old value', 'old_value', 20], ['New value', 'new_value', 20], ['When', 'created_at', 22]],
    edits.map(e => ({ ...e, old_value: JSON.stringify(e.old_value), new_value: JSON.stringify(e.new_value), created_at: new Date(e.created_at).toISOString() })))

  return Buffer.from(await book.xlsx.writeBuffer())
}

module.exports = { buildJson, buildXlsx, checkRows }
