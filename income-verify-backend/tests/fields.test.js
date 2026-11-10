const assert = require('node:assert/strict')
const { describe, it } = require('node:test')
const { applyEdits, getAt } = require('../src/fields')

const payslip = () => ({ employee_name: 'Asha Rao', net_pay: 44516, gross: 47000, earnings: [{ name: 'Basic', amount: 20700 }], page: 1 })
const statement = () => ({
  account: { account_holder: 'ASHA RAO', closing_balance: 45365.02, ifsc_valid: true },
  transactions: [{ row: 0, debit: 6900, credit: null, amount: -6900, balance: 117990.2 }],
})

describe('applyEdits', () => {
  it('edits top-level, nested and array paths, keeping numbers numeric', () => {
    const { fields, changes } = applyEdits(payslip(), [
      { path: 'net_pay', value: '44,616.00' },
      { path: 'earnings.0.amount', value: 20800 },
      { path: 'employee_name', value: '  Asha R Rao ' },
    ])
    assert.equal(fields.net_pay, 44616)
    assert.equal(getAt(fields, 'earnings.0.amount'), 20800)
    assert.equal(fields.employee_name, 'Asha R Rao')
    assert.equal(changes.length, 3)
    assert.deepEqual(changes[0], { path: 'net_pay', old: 44516, new: 44616 })
  })

  it('does not touch the input and skips values that did not change', () => {
    const original = payslip()
    const { changes } = applyEdits(original, [{ path: 'net_pay', value: 44516 }, { path: 'gross', value: 47100 }])
    assert.equal(original.gross, 47000)
    assert.deepEqual(changes.map(c => c.path), ['gross'])
  })

  it('recomputes a transaction amount from its debit and credit', () => {
    const { fields } = applyEdits(statement(), [{ path: 'transactions.0.debit', value: null }, { path: 'transactions.0.credit', value: '1,250.50' }])
    assert.equal(fields.transactions[0].amount, 1250.5)
  })

  it('rejects unknown paths, groups and non-numbers in amounts', () => {
    assert.throws(() => applyEdits(payslip(), [{ path: 'bonus', value: 1 }]), /No field bonus/)
    assert.throws(() => applyEdits(payslip(), [{ path: 'earnings.4.amount', value: 1 }]), /No field/)
    assert.throws(() => applyEdits(payslip(), [{ path: 'earnings', value: 'x' }]), /group of fields/)
    assert.throws(() => applyEdits(payslip(), [{ path: 'net_pay', value: 'lots' }]), /must be a number/)
  })

  it('treats a typed number in an empty field as a number', () => {
    const { fields } = applyEdits(statement(), [{ path: 'transactions.0.credit', value: '500' }])
    assert.equal(fields.transactions[0].credit, 500)
  })

  it('keeps booleans boolean', () => {
    const { fields } = applyEdits(statement(), [{ path: 'account.ifsc_valid', value: 'false' }])
    assert.equal(fields.account.ifsc_valid, false)
  })
})
