const { HttpError } = require('./middleware/error')

/**
 * Reviewer edits to a document's extracted fields. A path is a dot path into documents.fields
 * ("net_pay", "account.closing_balance", "transactions.12.debit"); only fields that already exist
 * can be edited. The worker re-runs every check on the corrected fields, so nothing is recalculated
 * here except a transaction's signed amount, which is derived from its debit and credit.
 */

const NUMBER_RE = /^-?[\d,]*\.?\d+$/

function walk(fields, path) {
  const parts = path.split('.')
  let parent = fields
  for (const part of parts.slice(0, -1)) {
    parent = parent?.[Array.isArray(parent) ? Number(part) : part]
    if (parent == null || typeof parent !== 'object') return null
  }
  const last = parts.at(-1)
  const key = Array.isArray(parent) ? Number(last) : last
  return Object.prototype.hasOwnProperty.call(parent, key) ? { parent, key } : null
}

const getAt = (fields, path) => {
  const spot = walk(fields, path)
  return spot ? spot.parent[spot.key] : undefined
}

// Numbers stay numbers: "45,365.02" typed into an amount becomes 45365.02.
function coerce(path, old, value) {
  if (value === null || value === '') return null
  if (typeof old === 'number' || (old === null && typeof value === 'string' && NUMBER_RE.test(value.trim()))) {
    const n = typeof value === 'number' ? value : Number(String(value).replace(/,/g, '').trim())
    if (!Number.isFinite(n)) throw new HttpError(400, `${path} must be a number`)
    return n
  }
  if (typeof old === 'boolean') return value === true || value === 'true'
  if (typeof old === 'object' && old !== null) throw new HttpError(400, `${path} is a group of fields; edit its parts`)
  return typeof value === 'string' ? value.trim() : value
}

/** Apply edits to a copy of `fields`. Returns the new fields and one change per value that really changed. */
function applyEdits(fields, edits) {
  const next = structuredClone(fields)
  const changes = []
  for (const { path, value } of edits) {
    const spot = walk(next, path)
    if (!spot) throw new HttpError(400, `No field ${path} on this document`)
    const old = spot.parent[spot.key]
    const updated = coerce(path, old, value)
    if (updated === old) continue
    spot.parent[spot.key] = updated
    changes.push({ path, old, new: updated })

    const row = path.match(/^transactions\.(\d+)\.(debit|credit)$/)
    if (row) {
      const t = next.transactions[Number(row[1])]
      t.amount = Math.round(((t.credit || 0) - (t.debit || 0)) * 100) / 100
    }
  }
  return { fields: next, changes }
}

module.exports = { applyEdits, getAt }
