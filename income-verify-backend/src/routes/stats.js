const express = require('express')
const db = require('../db')
const { EVAL_HEADLINE } = require('../config')
const { wrap } = require('../middleware/error')

const router = express.Router()

const round = (n, places) => (n == null ? null : Math.round(n * 10 ** places) / 10 ** places)

/**
 * Straight-through = an analysed application that came out verified (or was approved) with no reviewer
 * edit. Cost and time are per analysed application, summed over every task run for it and its documents.
 */
router.get('/', wrap(async (_req, res) => {
  const [docs, apps, spend] = await Promise.all([
    db.one(`SELECT count(*) FILTER (WHERE status = 'completed') AS processed, count(*) FILTER (WHERE status = 'failed') AS failed,
                   coalesce(sum(pages) FILTER (WHERE status = 'completed'), 0) AS pages FROM documents`),
    db.one(`SELECT count(*) AS total,
                   count(*) FILTER (WHERE analyzed_at IS NOT NULL) AS analysed,
                   count(*) FILTER (WHERE status = 'verified') AS verified,
                   count(*) FILTER (WHERE status = 'needs_review') AS needs_review,
                   count(*) FILTER (WHERE status = 'flagged') AS flagged,
                   count(*) FILTER (WHERE status = 'approved') AS approved,
                   count(*) FILTER (WHERE analyzed_at IS NOT NULL AND status IN ('verified', 'approved')
                                    AND NOT EXISTS (SELECT 1 FROM field_edits e JOIN documents d ON d.id = e.document_id WHERE d.application_id = a.id)) AS straight_through
              FROM applications a`),
    db.one(`WITH per_app AS (
              SELECT a.id, sum(u.cost_usd) AS cost, sum(u.duration_s) AS seconds
                FROM applications a
                JOIN usage_log u ON u.ref_id = a.id OR u.ref_id IN (SELECT id FROM documents WHERE application_id = a.id)
               WHERE a.analyzed_at IS NOT NULL
               GROUP BY a.id)
            SELECT avg(cost) AS avg_cost_usd, avg(seconds) AS avg_seconds, coalesce(sum(cost), 0) AS total_cost_usd FROM per_app`),
  ])
  res.json({
    documents: docs,
    applications: { ...apps, straight_through_pct: apps.analysed ? round((100 * apps.straight_through) / apps.analysed, 1) : null },
    avg_cost_usd: round(spend.avg_cost_usd, 4),
    avg_seconds: round(spend.avg_seconds, 1),
    total_cost_usd: round(spend.total_cost_usd, 4),
    evals: EVAL_HEADLINE,
  })
}))

module.exports = router
