const multer = require('multer')
const { PDFDocument } = require('pdf-lib')
const { FILE_TYPES, MAX_FILE_MB, MAX_FILES_PER_UPLOAD, MAX_PAGES } = require('./config')
const { HttpError } = require('./middleware/error')

const extOf = name => (name.match(/\.([a-z0-9]+)$/i)?.[1] || '').toLowerCase()

// PDFs and images only, held in memory just long enough to check and store them.
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: MAX_FILE_MB * 1024 * 1024, files: MAX_FILES_PER_UPLOAD },
  fileFilter: (_req, file, cb) => {
    const ok = extOf(file.originalname) in FILE_TYPES
    cb(ok ? null : new HttpError(400, `${file.originalname}: only PDF, PNG, JPG or WEBP files are accepted`), ok)
  },
})

/** What the first bytes say the file is — the extension alone can lie. */
function sniff(buffer) {
  if (buffer.subarray(0, 5).toString('latin1') === '%PDF-') return 'pdf'
  if (buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return 'png'
  if (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return 'jpg'
  if (buffer.subarray(0, 4).toString('latin1') === 'RIFF' && buffer.subarray(8, 12).toString('latin1') === 'WEBP') return 'webp'
  return null
}

async function pageCount(buffer) {
  const pdf = await PDFDocument.load(buffer, { ignoreEncryption: true, updateMetadata: false })
  return pdf.getPageCount()
}

/** Throw a 400 unless the file's content matches its extension and a PDF is within the page cap. */
async function checkFile(file) {
  const ext = extOf(file.originalname)
  const actual = sniff(file.buffer)
  const expected = ext === 'jpeg' ? 'jpg' : ext
  if (actual !== expected) throw new HttpError(400, `${file.originalname} is not a valid ${ext.toUpperCase()} file`)
  if (actual !== 'pdf') return 1
  let pages
  try {
    pages = await pageCount(file.buffer)
  } catch {
    throw new HttpError(400, `${file.originalname} could not be opened as a PDF`)
  }
  if (pages > MAX_PAGES) throw new HttpError(400, `${file.originalname} has ${pages} pages; the limit is ${MAX_PAGES}`)
  return pages
}

// "Payslip Jul (1).pdf" → "Payslip_Jul_1.pdf": safe as part of a storage key.
const safeName = name => name.normalize('NFKD').replace(/[^\w.-]+/g, '_').replace(/_+/g, '_').replace(/^_|_(?=\.)/g, '').slice(-80) || 'file'

module.exports = { upload, sniff, checkFile, safeName, extOf }
