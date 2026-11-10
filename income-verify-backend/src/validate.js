const { z } = require('zod')
const { HttpError } = require('./middleware/error')

const text = max => z.string().trim().max(max)

const schemas = {
  id: z.string().uuid(),

  createApplication: z.object({
    applicant_name: text(120).min(1, 'Applicant name is required'),
    declared_employer: text(160).default(''),
    // Form fields arrive as strings; "" means not given.
    declared_monthly_income: z.preprocess(
      v => (v === '' || v == null ? null : typeof v === 'string' ? Number(v.replace(/,/g, '')) : v),
      z.number({ invalid_type_error: 'Declared income must be a number' }).positive().max(1e8).nullable(),
    ).default(null),
  }),

  listApplications: z.object({
    status: z.enum(['draft', 'processing', 'verified', 'needs_review', 'flagged', 'approved', 'failed']).optional(),
    q: text(120).optional(),
    limit: z.coerce.number().int().min(1).max(200).default(100),
  }),

  // Field paths are dot paths into documents.fields: net_pay, account.closing_balance, transactions.12.debit.
  fieldEdits: z.object({
    edits: z.array(z.object({
      path: z.string().regex(/^[a-z_]+(\.[a-z0-9_]+)*$/, 'Bad field path').max(80),
      value: z.union([z.number(), z.string().max(300), z.null()]),
    })).min(1).max(100),
  }),

  exportQuery: z.object({ format: z.enum(['json', 'xlsx']).default('json') }),
}

/** Parse `data` with a named schema, or throw a 400 with the first problem. */
function parse(name, data) {
  const result = schemas[name].safeParse(data)
  if (result.success) return result.data
  const issue = result.error.issues[0]
  const where = issue.path.length ? `${issue.path.join('.')}: ` : ''
  throw new HttpError(400, name === 'id' ? 'Not found' : `${where}${issue.message}`)
}

// Route ids are uuids; anything else can't exist, so it is a 404 rather than a Postgres error.
function parseId(value) {
  if (!schemas.id.safeParse(value).success) throw new HttpError(404, 'Not found')
  return value
}

module.exports = { parse, parseId }
