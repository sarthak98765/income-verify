// Which extracted fields the review screen shows for each document type, in reading order.
// kind: 'money' (₹, editable number) | 'text'. Paths are dot paths into documents.fields.

export const LAYOUTS = {
  payslip: {
    sections: [
      { title: 'Employee and employer', fields: [
        ['employee_name', 'Employee name'], ['employee_id', 'Employee ID'], ['pan', 'PAN'], ['employer_name', 'Employer'],
        ['employer_cin', 'Employer CIN'], ['work_state', 'Work state'], ['month', 'Pay month'], ['bank_account', 'Salary account'],
      ] },
    ],
    lines: [['earnings', 'Earnings'], ['deductions', 'Deductions']],
    totals: [['gross', 'Gross earnings'], ['total_deductions', 'Total deductions'], ['net_pay', 'Net pay']],
  },
  bank_statement: {
    sections: [
      { title: 'Account', fields: [
        ['account.bank_name', 'Bank'], ['account.branch', 'Branch'], ['account.account_holder', 'Account holder'], ['account.account_number', 'Account number'],
        ['account.ifsc', 'IFSC'], ['account.period_from', 'Period from'], ['account.period_to', 'Period to'],
      ] },
    ],
    totals: [['account.opening_balance', 'Opening balance'], ['account.closing_balance', 'Closing balance']],
    transactions: true,
  },
  form16: {
    sections: [
      { title: 'Employee and employer', fields: [
        ['employee_name', 'Employee name'], ['employee_pan', 'Employee PAN'], ['employer_name', 'Employer'], ['employer_tan', 'Employer TAN'],
        ['assessment_year', 'Assessment year'], ['regime', 'Tax regime'],
      ] },
    ],
    totals: [
      ['gross_salary', 'Gross salary'], ['exemptions_section_10', 'Exemptions (section 10)'], ['standard_deduction', 'Standard deduction'],
      ['professional_tax', 'Professional tax'], ['chapter_via_deductions', 'Chapter VI-A deductions'], ['taxable_income', 'Taxable income'], ['tax_deducted', 'Tax deducted'],
    ],
  },
}

export function getAt(obj, path) {
  return path.split('.').reduce((v, k) => (v == null ? undefined : v[Array.isArray(v) ? Number(k) : k]), obj)
}

// What the reviewer sees in the input before editing.
export const toInput = v => (v == null ? '' : String(v))

/** Checks (not passed) and confidence reasons that put a field or row in doubt. */
export function doubtsFor(doc, path) {
  const reasons = []
  const conf = doc.confidence?.fields?.[path]
  if (conf?.level === 'low') reasons.push(...conf.reasons)
  for (const c of doc.checks || []) {
    if (c.status === 'pass') continue
    if ((c.fields || []).some(f => path === f || path.startsWith(`${f}.`))) reasons.push(c.message)
  }
  return [...new Set(reasons)]
}
