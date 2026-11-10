const assert = require('node:assert/strict')
const { describe, it } = require('node:test')
const { PDFDocument } = require('pdf-lib')
const { sniff, checkFile, safeName } = require('../src/upload')
const { parse, parseId } = require('../src/validate')
const storage = require('../src/storage')

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0])

async function pdfWith(pages) {
  const pdf = await PDFDocument.create()
  for (let i = 0; i < pages; i += 1) pdf.addPage()
  return Buffer.from(await pdf.save())
}

describe('upload guards', () => {
  it('sniffs file types from their first bytes', () => {
    assert.equal(sniff(Buffer.from('%PDF-1.7 ...')), 'pdf')
    assert.equal(sniff(PNG), 'png')
    assert.equal(sniff(Buffer.from([0xff, 0xd8, 0xff, 0xe0])), 'jpg')
    assert.equal(sniff(Buffer.from('RIFF\0\0\0\0WEBPVP8 ')), 'webp')
    assert.equal(sniff(Buffer.from('MZ executable')), null)
  })

  it('rejects a file whose content does not match its extension', async () => {
    await assert.rejects(checkFile({ originalname: 'slip.pdf', buffer: PNG }), /not a valid PDF/)
    assert.equal(await checkFile({ originalname: 'slip.PNG', buffer: PNG }), 1)
  })

  it('counts PDF pages and enforces the page cap', async () => {
    assert.equal(await checkFile({ originalname: 'a.pdf', buffer: await pdfWith(3) }), 3)
    await assert.rejects(checkFile({ originalname: 'big.pdf', buffer: await pdfWith(31) }), /31 pages; the limit is 30/)
    await assert.rejects(checkFile({ originalname: 'broken.pdf', buffer: Buffer.from('%PDF-1.4 garbage') }), /could not be opened/)
  })

  it('makes file names safe for storage keys', () => {
    assert.equal(safeName('Payslip Jul (1).pdf'), 'Payslip_Jul_1.pdf')
    assert.ok(!safeName('../../etc/passwd').includes('/'))
    assert.ok(!safeName('a/b\\c.pdf').includes('/'))
  })

  it('keeps storage keys inside the storage folder', () => {
    assert.throws(() => storage.pathFor('../outside.txt'), /escapes storage/)
    assert.ok(storage.pathFor('uploads/x/y.pdf').endsWith('uploads/x/y.pdf'))
    return assert.rejects(storage.removeFolder('uploads'), /refusing/)
  })
})

describe('validation', () => {
  it('parses a new application from form strings', () => {
    const body = parse('createApplication', { applicant_name: ' Asha ', declared_monthly_income: '45,000' })
    assert.deepEqual(body, { applicant_name: 'Asha', declared_employer: '', declared_monthly_income: 45000 })
    assert.equal(parse('createApplication', { applicant_name: 'A', declared_monthly_income: '' }).declared_monthly_income, null)
  })

  it('rejects bad input with a readable message', () => {
    assert.throws(() => parse('createApplication', { applicant_name: '' }), /applicant_name: Applicant name is required/)
    assert.throws(() => parse('createApplication', { applicant_name: 'A', declared_monthly_income: 'abc' }), /must be a number/)
    assert.throws(() => parse('fieldEdits', { edits: [{ path: 'net_pay; DROP', value: 1 }] }), /Bad field path/)
    assert.throws(() => parse('exportQuery', { format: 'csv' }), /format/)
  })

  it('treats a non-uuid id as not found', () => {
    assert.throws(() => parseId('123'), /Not found/)
    assert.equal(parseId('0b8f2a39-5c1e-4d5e-9a63-2f1d3c4b5a69'), '0b8f2a39-5c1e-4d5e-9a63-2f1d3c4b5a69')
  })
})
