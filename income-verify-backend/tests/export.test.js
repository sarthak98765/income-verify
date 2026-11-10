const assert = require('node:assert/strict')
const { describe, it } = require('node:test')
const ExcelJS = require('exceljs')
const { buildJson, buildXlsx, checkRows } = require('../src/export')

const app = {
  id: '0b8f2a39-5c1e-4d5e-9a63-2f1d3c4b5a69', applicant_name: 'Asha Rao', declared_employer: 'Bali Logistics', declared_monthly_income: 44516,
  status: 'verified', authenticity_score: 95, verified_monthly_income: 44516, foir: 0.35, progress: { stage: 'done' }, usage: { cost_usd: 0.05 },
  metrics: { salary_months_matched: 3, salary_months_checked: 3, average_balance: 24555.64, emi_total: 15714, bounces: [], months_covered: 6 },
  salary_matches: [{ month: '2026-07', net_pay: 44516, credit: { date: '2026-07-28', amount: 44516, description: 'NEFT SALARY' } }],
  cross_checks: [{ key: 'salary_credit', status: 'pass', message: 'ok', page: 2 }],
  signals: [], reasons: [], summary: 'Verified.', created_at: new Date(),
}
const docs = [
  { id: 'd1', filename: 'payslip.pdf', doc_type: 'payslip', pages: 1, status: 'completed', raw: { secret: 1 }, fields: { month: '2026-07', net_pay: 44516, gross: 47000, total_deductions: 2484 }, checks: [{ key: 'payslip_net_pay', status: 'pass', message: 'ok' }], signals: [], confidence: {} },
  { id: 'd2', filename: 'bank.pdf', doc_type: 'bank_statement', pages: 3, status: 'completed', raw: {}, fields: { account: {}, transactions: [{ date: '2026-07-28', description: 'NEFT SALARY', credit: 44516, debit: null, balance: 50000, page: 2 }] }, checks: [], signals: [], confidence: {} },
]

describe('export', () => {
  it('leaves internal columns out of the JSON', () => {
    const out = buildJson(app, docs, [])
    assert.equal(out.application.applicant_name, 'Asha Rao')
    assert.equal(out.application.progress, undefined)
    assert.equal(out.documents[0].raw, undefined)
    assert.equal(out.documents[0].fields.net_pay, 44516)
  })

  it('lists cross-document checks before each document\'s own', () => {
    assert.deepEqual(checkRows(app, docs).map(r => r.source), ['Across documents', 'payslip.pdf'])
  })

  it('builds a workbook with one sheet per view', async () => {
    const buffer = await buildXlsx(app, docs, [{ filename: 'payslip.pdf', field_path: 'net_pay', old_value: 1, new_value: 2, created_at: new Date() }])
    const book = new ExcelJS.Workbook()
    await book.xlsx.load(buffer)
    assert.deepEqual(book.worksheets.map(w => w.name), ['Summary', 'Checks', 'Fraud signals', 'Salary matches', 'Payslips', 'Transactions', 'Reviewer edits'])
    assert.equal(book.getWorksheet('Transactions').getRow(2).getCell(5).value, 44516)
    assert.equal(book.getWorksheet('Payslips').rowCount, 2)
  })
})
