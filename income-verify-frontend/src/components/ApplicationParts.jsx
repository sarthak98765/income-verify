import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, ChevronDown, ChevronRight, FileText, Image as ImageIcon, Loader2 } from 'lucide-react'
import { DOC_TYPES, fmtDate, fmtDay, fmtMonth, humanize, pct, rupees, seconds, usd } from '@/lib/format'
import { isActive } from '@/lib/progress'
import { buildFindings, docLabel, reviewLink, verdictSentence } from '@/lib/findings'
import { Card, CheckIcon, StatusBadge, TONES, VERDICTS, scoreTone } from '@/components/ui'

/** The blocks of the application page: live run, decision sheet, salary credits, bank behaviour, checks, documents. */

// ── Live run ─────────────────────────────────────────────────────────────────

const DOC_STEPS = ['Read', 'Extract', 'Check']
const STAGE_STEP = { queued: -1, reading: 0, classifying: 0, extracting: 1, categorising: 1, rechecking: 2, checking: 2 }

function stageLine(d) {
  const p = d.progress || {}
  const type = (DOC_TYPES[p.doc_type || d.doc_type] || 'document').toLowerCase()
  if (d.status === 'queued' || p.stage === 'queued') return 'Waiting for a worker'
  switch (p.stage) {
    case 'reading': return 'Reading the pages with OCR'
    case 'classifying': return 'Working out what kind of document this is'
    case 'extracting': return `Copying the ${type} values as printed`
    case 'categorising': return `Sorting ${p.rows ?? ''} transactions into salary, EMI, rent and the rest`.replace('  ', ' ')
    case 'rechecking': return p.doc_type === 'payslip' || d.doc_type === 'payslip' ? 'Reading the totals again from the image' : 'Re-reading rows where the balance does not add up'
    case 'checking': return 'Running the checks'
    default: return d.status === 'processing' ? 'Reading the pages with OCR' : 'Starting'
  }
}

function docStep(d) {
  if (d.status === 'completed') return 3
  if (d.status === 'failed') return 3
  const step = STAGE_STEP[d.progress?.stage] ?? -1
  return d.status === 'processing' ? Math.max(0, step) : step
}

function useElapsed(since) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])
  const s = Math.max(0, Math.round((now - new Date(since).getTime()) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function Track({ step, failed }) {
  return (
    <div className="grid w-full grid-cols-3 gap-1">
      {DOC_STEPS.map((label, i) => {
        const done = i < step
        const current = i === step
        return (
          <div key={label} className={`relative h-1 overflow-hidden rounded-full ${failed ? 'bg-bad/60' : done ? 'bg-ink' : 'bg-line'}`} title={label}>
            {current && !failed && <span className="absolute inset-y-0 left-0 w-2/5 rounded-full bg-brand-600 animate-sweep" />}
          </div>
        )
      })}
    </div>
  )
}

export function LiveRun({ app }) {
  const docs = app.documents || []
  const reading = docs.some(d => isActive(d.status))
  const since = docs.filter(d => isActive(d.status)).map(d => d.created_at).sort()[0] || app.updated_at
  const elapsed = useElapsed(since)
  const analysing = !reading && app.status === 'processing'
  const done = docs.filter(d => d.status === 'completed').length
  return (
    <section className="overflow-hidden rounded-lg border border-line bg-surface" aria-live="polite">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line px-5 py-4 sm:px-6">
        <div>
          <h2 className="font-serif text-2xl text-ink">{analysing ? 'Checking the documents against each other' : 'Reading the documents'}</h2>
          <p className="mt-0.5 text-sm text-ink-3">{analysing ? 'Salary credits, names, employer and annual income, then the verdict.' : `${done} of ${docs.length} read. This page updates by itself.`}</p>
        </div>
        <div className="text-right">
          <div className="num font-serif text-3xl text-ink">{elapsed}</div>
          <div className="text-xs text-ink-3">usually about 2 minutes</div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {docs.map(d => {
          const step = docStep(d)
          const failed = d.status === 'failed'
          const Icon = d.mime?.startsWith('image/') ? ImageIcon : FileText
          return (
            <li key={d.id} className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 px-5 py-3.5 sm:grid-cols-[auto_minmax(0,1fr)_minmax(0,1.3fr)_9rem] sm:px-6">
              <Icon className={`h-[18px] w-[18px] ${d.status === 'completed' ? 'text-ink' : 'text-ink-3'}`} />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink">{d.status === 'completed' ? docLabel(d) : d.filename}</div>
                {d.status === 'completed' && <div className="truncate text-xs text-ink-3">{d.filename}</div>}
              </div>
              <div className={`col-start-2 min-w-0 truncate text-sm sm:col-start-auto ${failed ? 'text-bad' : 'text-ink-2'}`}>
                {failed ? d.error || 'Could not be read' : d.status === 'completed' ? <span className="inline-flex items-center gap-1.5 text-ink-3"><Check className="h-3.5 w-3.5 text-ok" />Read and checked</span> : stageLine(d)}
              </div>
              <div className="col-start-2 sm:col-start-auto"><Track step={step} failed={failed} /></div>
            </li>
          )
        })}
        <li className={`flex items-center gap-4 px-5 py-3.5 sm:px-6 ${analysing ? '' : 'opacity-50'}`}>
          {analysing ? <Loader2 className="h-[18px] w-[18px] animate-spin text-brand-600" /> : <span className="h-[18px] w-[18px] rounded-full border border-dashed border-ink-3" />}
          <span className="text-sm font-medium text-ink">Cross-check and decide</span>
          <span className="text-sm text-ink-3">{analysing ? (app.progress?.stage === 'summarising' ? 'Writing the note for the underwriter' : 'Matching salary credits and names across documents') : 'After every document is read'}</span>
        </li>
      </ul>
    </section>
  )
}

// ── Decision sheet ───────────────────────────────────────────────────────────

function Stamp({ status }) {
  const v = VERDICTS[status] || VERDICTS.draft
  const t = TONES[v.tone]
  return (
    <div className={`inline-flex -rotate-[4deg] items-center gap-2.5 rounded-md border-[2.5px] px-4 py-1.5 animate-stamp border-current ${t.text}`}>
      <v.icon className="h-6 w-6" strokeWidth={2.2} />
      <span className="font-serif text-[2rem] font-semibold uppercase leading-none tracking-[0.06em]">{v.label}</span>
    </div>
  )
}

function ScoreDial({ score }) {
  const tone = scoreTone(score)
  const r = 30
  const c = 2 * Math.PI * r
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 72 72" className="h-[72px] w-[72px] -rotate-90" aria-hidden>
        <circle cx="36" cy="36" r={r} fill="none" strokeWidth="6" className="stroke-line" />
        <circle cx="36" cy="36" r={r} fill="none" strokeWidth="6" strokeLinecap="round" className={`${TONES[tone].text} stroke-current transition-all duration-700`} strokeDasharray={c} strokeDashoffset={c * (1 - (score ?? 0) / 100)} />
      </svg>
      <div>
        <div className={`num font-serif text-[2rem] leading-none ${TONES[tone].text}`}>{score ?? '–'}<span className="text-base text-ink-3"> / 100</span></div>
        <div className="mt-1 text-xs text-ink-3">Authenticity score</div>
      </div>
    </div>
  )
}

function Finding({ f }) {
  const body = (
    <>
      <span className={`num mt-0.5 w-9 shrink-0 text-right text-xs font-semibold ${f.weight ? 'text-bad' : 'text-ink-3'}`}>{f.weight ? `−${f.weight}` : f.confirm ? 'check' : 'note'}</span>
      <span className="min-w-0 flex-1 text-[15px] leading-snug text-ink">{f.text}</span>
      {f.doc && (
        <span className="hidden shrink-0 items-center gap-1 text-xs text-ink-3 group-hover:text-brand-600 sm:inline-flex">
          {docLabel(f.doc)}{f.page ? `, page ${f.page}` : ''}<ChevronRight className="h-3.5 w-3.5" />
        </span>
      )}
    </>
  )
  return (
    <li>
      {f.doc
        ? <Link to={reviewLink(f.doc, f)} className="group -mx-2 flex items-start gap-4 rounded-md px-2 py-2.5 hover:bg-subtle">{body}</Link>
        : <div className="-mx-2 flex items-start gap-4 px-2 py-2.5">{body}</div>}
    </li>
  )
}

function Figure({ label, value, note, tone }) {
  return (
    <div className="min-w-0 px-5 py-4 sm:px-6">
      <div className="text-xs text-ink-3">{label}</div>
      <div className={`num mt-1 font-serif text-[1.65rem] leading-tight ${tone || 'text-ink'}`}>{value}</div>
      {note && <div className="mt-0.5 truncate text-xs text-ink-3" title={typeof note === 'string' ? note : undefined}>{note}</div>}
    </div>
  )
}

export function DecisionSheet({ app }) {
  const findings = buildFindings(app)
  const m = app.metrics || {}
  const declared = app.declared_monthly_income
  const verified = app.verified_monthly_income
  const gap = declared && verified != null ? (verified - declared) / declared : null
  const foirTone = m.foir == null ? '' : m.foir > 0.6 ? TONES.bad.text : m.foir > 0.5 ? TONES.warn.text : ''
  const bounces = (m.bounces || []).length
  const v = VERDICTS[app.status]
  const shownStatus = app.status === 'approved' ? 'approved' : app.status
  return (
    <section className={`overflow-hidden rounded-lg border bg-surface ${TONES[v?.tone || 'neutral'].border}`}>
      <div className={`grid gap-6 px-5 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] ${TONES[v?.tone || 'neutral'].soft}`}>
        <div className="min-w-0">
          <Stamp status={shownStatus} />
          <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-ink">
            {app.status === 'approved' ? `Signed off on ${fmtDate(app.approved_at)}. Fields are locked.` : verdictSentence(app, findings)}
          </p>
        </div>
        <ScoreDial score={app.authenticity_score} />
      </div>
      {findings.length > 0 && (
        <div className="border-t border-line px-5 py-3 sm:px-6">
          <h3 className="pt-1 text-sm font-medium text-ink-3">{findings.length === 1 ? 'Finding' : `${findings.length} findings`}, by how much they lower the score</h3>
          <ul className="mt-1">{findings.map((f, i) => <Finding key={i} f={f} />)}</ul>
        </div>
      )}
      <div className="grid grid-cols-2 divide-line border-t border-line sm:grid-cols-3 lg:grid-cols-5 lg:divide-x [&>*]:border-line max-lg:[&>*:nth-child(n+3)]:border-t sm:max-lg:[&>*:nth-child(3)]:border-t-0">
        <Figure label="Verified income a month" value={rupees(verified)} note={declared ? `Declared ${rupees(declared)}${gap != null && Math.abs(gap) >= 0.005 ? `, ${gap > 0 ? '+' : '−'}${pct(Math.abs(gap), 0)}` : ''}` : 'No declared income'} tone={gap != null && gap < -0.1 ? TONES.bad.text : ''} />
        <Figure label="Salary credits found" value={m.salary_months_checked != null ? `${m.salary_months_matched} of ${m.salary_months_checked}` : '–'} note="payslip net pay seen in the bank" tone={m.salary_months_checked && m.salary_months_matched < m.salary_months_checked ? TONES.bad.text : ''} />
        <Figure label="FOIR" value={pct(m.foir, 1)} note="existing EMIs over income" tone={foirTone} />
        <Figure label="Existing EMIs a month" value={rupees(m.emi_total)} note={`${(m.existing_emis || []).length} recurring debit${(m.existing_emis || []).length === 1 ? '' : 's'}`} />
        <Figure label="Bounces" value={bounces} note={m.months_covered ? `over ${m.months_covered} months` : null} tone={bounces ? TONES.bad.text : ''} />
      </div>
    </section>
  )
}

// ── Detail blocks ────────────────────────────────────────────────────────────

export function SalaryMatches({ matches }) {
  if (!matches?.length) return null
  return (
    <Card title="Salary credits" subtitle="Each payslip's net pay, looked for in the bank statement." padded={false}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-ink-3">
            <tr><th className="px-5 py-2 font-medium">Month</th><th className="px-3 py-2 text-right font-medium">Payslip net pay</th><th className="px-3 py-2 font-medium">In the bank</th><th className="px-5 py-2 text-right font-medium">Credit</th></tr>
          </thead>
          <tbody>
            {matches.map(s => (
              <tr key={s.month} className={`border-t border-line ${s.credit ? '' : 'bg-bad/[0.05]'}`}>
                <td className="px-5 py-2.5 text-ink">{fmtMonth(s.month)}</td>
                <td className="num px-3 py-2.5 text-right text-ink">{rupees(s.net_pay, true)}</td>
                <td className="px-3 py-2.5">
                  {s.credit
                    ? <span className="inline-flex items-center gap-1.5 text-ink-2"><CheckIcon status="pass" />{fmtDay(s.credit.date)}</span>
                    : <span className="inline-flex items-center gap-1.5 font-medium text-bad"><CheckIcon status="fail" />Not found</span>}
                </td>
                <td className="num px-5 py-2.5 text-right text-ink">{s.credit ? rupees(s.credit.amount, true) : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function BankBehaviour({ app }) {
  const m = app.metrics || {}
  const emis = m.existing_emis || []
  const bounces = m.bounces || []
  if (m.average_balance == null && !emis.length) return null
  return (
    <Card title="Bank behaviour" subtitle={m.months_covered ? `From ${m.months_covered} months of statement.` : null}>
      <dl className="grid grid-cols-3 gap-4 border-b border-line pb-4 text-sm">
        <div><dt className="text-xs text-ink-3">Average balance</dt><dd className="num mt-0.5 font-medium text-ink">{rupees(m.average_balance)}</dd></div>
        <div><dt className="text-xs text-ink-3">Lowest balance</dt><dd className="num mt-0.5 font-medium text-ink">{rupees(m.minimum_balance)}</dd></div>
        <div><dt className="text-xs text-ink-3">Cash deposits</dt><dd className="num mt-0.5 font-medium text-ink">{pct(m.cash_deposit_share)} of credits</dd></div>
      </dl>
      {emis.length > 0 && (
        <div className="pt-4">
          <h3 className="mb-1 text-sm font-medium text-ink">Recurring EMIs</h3>
          <ul className="text-sm">
            {emis.map(e => (
              <li key={e.description + e.amount} className="flex items-center gap-3 border-t border-line py-2 first:border-0">
                <span className="min-w-0 flex-1 truncate text-ink-2" title={e.description}>{e.description}</span>
                <span className="shrink-0 text-xs text-ink-3">{e.months.length} months</span>
                <span className="num w-20 shrink-0 text-right font-medium text-ink">{rupees(e.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {bounces.length > 0 && (
        <div className="pt-4">
          <h3 className="mb-1 text-sm font-medium text-bad">Bounces</h3>
          <ul className="text-sm">
            {bounces.map((b, i) => <li key={i} className="flex gap-3 border-t border-line py-2 first:border-0"><span className="num shrink-0 text-ink-3">{fmtDay(b.date)}</span><span className="truncate text-ink-2">{b.description}</span></li>)}
          </ul>
        </div>
      )}
    </Card>
  )
}

const ORDER = { fail: 0, warn: 1, pass: 2 }

export function ChecksList({ app }) {
  const [open, setOpen] = useState(false)
  const groups = [
    { label: 'Across documents', doc: null, checks: app.cross_checks || [] },
    ...(app.documents || []).filter(d => d.checks?.length).map(d => ({ label: docLabel(d), doc: d, checks: d.checks })),
  ]
  const all = groups.flatMap(g => g.checks.map(c => ({ ...c, group: g })))
  if (!all.length) return null
  const problems = all.filter(c => c.status !== 'pass').sort((a, b) => ORDER[a.status] - ORDER[b.status])
  const passed = all.length - problems.length
  return (
    <Card title="Checks" subtitle={`${all.length} run, ${passed} passed${problems.length ? `, ${problems.length} need attention` : ''}.`} padded={false}>
      {problems.length > 0 && (
        <ul className="divide-y divide-line">
          {problems.map((c, i) => (
            <li key={i} className="flex gap-3 px-5 py-3 text-sm">
              <CheckIcon status={c.status} className="mt-0.5 h-4 w-4" />
              <div className="min-w-0 flex-1">
                <div className="text-ink">{c.message}</div>
                <div className="mt-0.5 text-xs text-ink-3">
                  {humanize(c.key)}, {c.group.doc ? <Link to={reviewLink(c.group.doc, { page: c.page, focus: c.fields?.[0] })} className="text-brand-600 hover:underline">{c.group.label}{c.page ? `, page ${c.page}` : ''}</Link> : c.group.label.toLowerCase()}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} className={`flex w-full items-center gap-2 px-5 py-3 text-sm font-medium text-ink-2 hover:bg-subtle hover:text-ink ${problems.length ? 'border-t border-line' : ''}`}>
        <ChevronDown className={`h-4 w-4 transition ${open ? 'rotate-180' : ''}`} />{open ? 'Hide' : 'Show'} the {passed} checks that passed
      </button>
      {open && (
        <div className="border-t border-line px-5 py-2">
          {groups.map(g => {
            const ok = g.checks.filter(c => c.status === 'pass')
            if (!ok.length) return null
            return (
              <div key={g.label} className="py-2">
                <h3 className="text-xs font-medium text-ink-3">{g.label}</h3>
                <ul className="mt-1 space-y-1">
                  {ok.map((c, i) => <li key={i} className="flex gap-2 text-sm text-ink-2"><Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" />{c.message}</li>)}
                </ul>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

export function UnderwriterNote({ app }) {
  if (!app.summary) return null
  return (
    <Card title="Note for the underwriter">
      <p className="whitespace-pre-line font-serif text-base leading-[1.65] text-ink">{app.summary}</p>
      <p className="mt-3 text-xs text-ink-3">
        {app.summary_by === 'model' ? 'Written by a small model from the computed facts. Every number in it was checked against them.' : 'The model note had a number that was not in the facts, so a template was used instead.'}
      </p>
    </Card>
  )
}

function factsLine(d) {
  const f = d.facts || {}
  if (d.doc_type === 'payslip') return f.net_pay != null ? `Net pay ${rupees(f.net_pay)}` : ''
  if (d.doc_type === 'bank_statement') return [f.bank, f.transactions != null && `${f.transactions} transactions`].filter(Boolean).join(', ')
  if (d.doc_type === 'form16') return [f.assessment_year && `AY ${f.assessment_year}`, f.gross_salary != null && `gross ${rupees(f.gross_salary)}`].filter(Boolean).join(', ')
  return ''
}

export function DocumentsList({ documents }) {
  return (
    <Card title="Documents" subtitle="Open one to see the page beside what was read from it." padded={false}>
      <ul className="divide-y divide-line">
        {documents.map(d => {
          const failed = (d.checks || []).filter(c => c.status === 'fail').length + (d.signals || []).length
          const low = (d.low_fields || []).length
          const Icon = d.mime?.startsWith('image/') ? ImageIcon : FileText
          return (
            <li key={d.id}>
              <Link to={`/documents/${d.id}`} className="group flex items-center gap-3 px-5 py-3 transition hover:bg-subtle">
                <Icon className="h-[18px] w-[18px] shrink-0 text-ink-3" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-ink group-hover:text-brand-600">{d.status === 'completed' ? docLabel(d) : d.filename}</div>
                  <div className="truncate text-xs text-ink-3">
                    {d.status === 'failed' ? <span className="text-bad">{d.error || 'Could not be read'}</span> : d.status === 'completed' ? factsLine(d) || d.filename : 'Reading'}
                  </div>
                </div>
                {failed > 0 && <span className="num rounded-full bg-bad/10 px-2 py-0.5 text-xs font-medium text-bad">{failed}</span>}
                {!failed && low > 0 && <span className="num rounded-full bg-warn/10 px-2 py-0.5 text-xs font-medium text-warn">{low}</span>}
                {d.status !== 'completed' && <StatusBadge status={d.status} size="sm" />}
                <ChevronRight className="h-4 w-4 shrink-0 text-ink-3" />
              </Link>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

export function RunDetails({ app }) {
  const t = app.totals || {}
  const rows = [
    ['AI cost', usd(t.cost_usd)],
    ['Processing time', seconds(t.processing_s)],
    ['Pages through OCR', t.ocr_pages ?? '–'],
    ['Model calls', t.llm_calls ?? '–'],
    ['Reviewer edits', app.edits_count ?? 0],
  ]
  return (
    <Card title="This run">
      <dl className="space-y-2 text-sm">
        {rows.map(([label, value]) => <div key={label} className="flex justify-between gap-3"><dt className="text-ink-3">{label}</dt><dd className="num font-medium text-ink">{value}</dd></div>)}
      </dl>
      {app.analyzed_at && <p className="mt-3 border-t border-line pt-3 text-xs text-ink-3">Analysed {fmtDate(app.analyzed_at)}. OCR is cached, so a re-run of the same file costs less.</p>}
    </Card>
  )
}

