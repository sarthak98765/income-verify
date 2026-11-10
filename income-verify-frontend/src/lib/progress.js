// The worker reports fine-grained stages (progress.py); the tracker shows four steps.
export const STEPS = ['Reading', 'Extracting', 'Checking', 'Analysing']

const STAGE_STEP = { queued: 0, reading: 0, classifying: 0, extracting: 1, categorising: 1, rechecking: 2, checking: 2, analysing: 3, summarising: 3 }

export const STAGE_TEXT = {
  queued: 'Waiting in queue',
  reading: 'Reading pages (OCR)',
  classifying: 'Working out the document type',
  extracting: 'Extracting fields',
  categorising: 'Categorising transactions',
  rechecking: 'Re-reading values that do not add up',
  checking: 'Running checks',
  analysing: 'Cross-checking documents',
  summarising: 'Writing the underwriter note',
  done: 'Done',
}

export const isActive = status => status === 'queued' || status === 'processing'

/** Which step a document is on: 0–2 while being read, 3 once read. */
export function documentStep(doc) {
  if (doc.status === 'completed' || doc.status === 'failed') return 3
  if (doc.status === 'queued') return 0
  return Math.min(2, STAGE_STEP[doc.progress?.stage] ?? 0)
}

/** The application's step: the slowest document while any is being read, then the analysis, then 4 (done). */
export function applicationStep(app) {
  const active = (app.documents || []).filter(d => isActive(d.status))
  if (active.length) return Math.min(...active.map(documentStep))
  if (app.status === 'processing') return 3
  return 4
}

export const stageText = stage => STAGE_TEXT[stage] || (stage ? stage[0].toUpperCase() + stage.slice(1) : '')
