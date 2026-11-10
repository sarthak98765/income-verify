import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Search, Upload, Users } from 'lucide-react'
import { api, errorMessage } from '@/lib/api'
import usePolling from '@/lib/usePolling'
import { pct, rupees, timeAgo } from '@/lib/format'
import { SampleStrip } from '@/components/SamplePicker'
import { Alert, EmptyState, ProgressBar, Segmented, Skeleton, StatusBadge, TONES, buttonClass, inputBase, scoreTone } from '@/components/ui'

// The pipeline in four steps. `by` says who does it: the core rule is that the model only reads.
const PIPELINE = [
  { title: 'Read every page', text: 'Mistral OCR, for PDFs, scans and phone photos', by: 'model' },
  { title: 'Copy values as printed', text: 'An OpenAI model fills a fixed schema, nothing is calculated', by: 'model' },
  { title: 'Check the maths and match documents', text: 'Payslip sums, PF and ESI, balance on every row, salary credits, Form 16', by: 'code' },
  { title: 'Decide and explain', text: 'Verdict, authenticity score and the reason for every flag', by: 'code' },
]

function Pipeline() {
  return (
    <ol className="relative space-y-5 border-l border-line pl-6">
      {PIPELINE.map((p, i) => (
        <li key={p.title} className="relative">
          <span className={`num absolute -left-[33px] flex h-[18px] w-[18px] items-center justify-center rounded-full text-[10px] font-semibold ring-4 ring-canvas ${p.by === 'model' ? 'bg-brand-600 text-white dark:text-canvas' : 'bg-ink text-canvas'}`}>{i + 1}</span>
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-[15px] font-medium text-ink">{p.title}</span>
            <span className={`text-xs font-medium ${p.by === 'model' ? 'text-brand-600' : 'text-ink-3'}`}>{p.by === 'model' ? 'AI model' : 'Python'}</span>
          </div>
          <p className="mt-0.5 text-sm text-ink-3">{p.text}</p>
        </li>
      ))}
    </ol>
  )
}

function Hero({ headline }) {
  return (
    <section className="grid gap-10 pb-2 lg:grid-cols-12 lg:gap-16">
      <div className="lg:col-span-7">
        <h1 className="max-w-2xl font-serif text-[2.6rem] font-normal leading-[1.08] tracking-tight text-ink sm:text-[3.4rem]">
          Check a borrower's income against their own documents.
        </h1>
        <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-ink-2">
          Upload payslips, a bank statement and Form 16. In about two minutes you get the verified monthly income, existing EMIs, FOIR and any sign of an edited document, each with the page it came from.
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-3">
          <Link to="/new" className={buttonClass('primary', 'lg')}><Upload className="h-4 w-4" />Upload documents</Link>
          <a href="#samples" className={buttonClass('secondary', 'lg')}>Try a sample applicant</a>
        </div>
        {headline?.length > 0 && (
          <dl className="mt-10 grid max-w-2xl grid-cols-2 gap-x-8 gap-y-5 border-t border-line pt-6 sm:grid-cols-4">
            {headline.map(h => (
              <div key={h.label}>
                <dt className="sr-only">{h.label}</dt>
                <dd className="num font-serif text-3xl text-ink">{h.value}</dd>
                <dd className="mt-1 text-xs leading-snug text-ink-3">{h.label}</dd>
              </div>
            ))}
          </dl>
        )}
        {headline?.length > 0 && <p className="mt-3 text-xs text-ink-3">Measured on 30 held-out synthetic applicants (v2). <Link to="/stats" className="font-medium text-brand-600 underline-offset-2 hover:underline">How it was tested</Link></p>}
      </div>
      <div className="lg:col-span-5 lg:pt-3">
        <h2 className="mb-5 text-sm font-medium text-ink-3">How a file is checked</h2>
        <Pipeline />
      </div>
    </section>
  )
}

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'flagged', label: 'Flagged', dot: 'bad' },
  { value: 'needs_review', label: 'Needs review', dot: 'warn' },
  { value: 'verified', label: 'Verified', dot: 'ok' },
  { value: 'approved', label: 'Approved', dot: 'brand' },
]

const uniqueReasons = a => [...new Set(a.reasons || [])]

function Score({ score }) {
  if (score == null) return <span className="text-sm text-ink-3">–</span>
  const tone = scoreTone(score)
  return (
    <div className="flex items-center gap-2.5" title={`Authenticity ${score} out of 100`}>
      <span className={`num w-7 text-right text-sm font-semibold ${TONES[tone].text}`}>{score}</span>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-line"><div className={`h-full ${TONES[tone].bar}`} style={{ width: `${Math.max(4, score)}%` }} /></div>
    </div>
  )
}

/** Verified income, and how far it is from what the applicant declared. */
function Income({ a, align = 'right' }) {
  const verified = a.verified_monthly_income
  const declared = a.declared_monthly_income
  let note = null
  if (verified != null && declared) {
    const diff = (verified - declared) / declared
    note = Math.abs(diff) < 0.02
      ? <span className="text-ink-3">as declared</span>
      : <span className={diff < -0.1 ? TONES.bad.text : TONES.warn.text}>{diff > 0 ? '+' : '−'}{Math.round(Math.abs(diff) * 100)}% vs declared</span>
  }
  return (
    <div className={align === 'right' ? 'text-right' : ''}>
      <div className="num text-sm font-medium text-ink">{rupees(verified)}</div>
      {note && <div className="text-xs">{note}</div>}
    </div>
  )
}

function DocsProgress({ a }) {
  if (!a.documents_count) return <span className="text-xs text-ink-3">No documents</span>
  const done = a.documents_done + a.documents_failed
  if (a.status !== 'processing' || done === a.documents_count) {
    return <span className="text-xs text-ink-3">{a.documents_count} files{a.documents_failed ? `, ${a.documents_failed} failed` : ''}</span>
  }
  return (
    <div className="w-24">
      <div className="num mb-1 text-xs text-ink-3">{done} of {a.documents_count} read</div>
      <ProgressBar value={done} max={a.documents_count} />
    </div>
  )
}

const foirTone = f => (f == null ? 'text-ink' : f > 0.6 ? TONES.bad.text : f > 0.5 ? TONES.warn.text : 'text-ink')

const SampleTag = () => <span className="rounded border border-line px-1.5 py-px text-[11px] font-medium text-ink-3">Sample</span>

function Row({ a }) {
  const navigate = useNavigate()
  const top = uniqueReasons(a)[0]
  return (
    <tr onClick={() => navigate(`/applications/${a.id}`)} className="group cursor-pointer border-t border-line align-top transition-colors hover:bg-subtle/60">
      <td className="py-3.5 pl-5 pr-4">
        <div className="flex items-center gap-2">
          <Link to={`/applications/${a.id}`} onClick={e => e.stopPropagation()} className="font-medium text-ink group-hover:text-brand-600">{a.applicant_name}</Link>
          {a.is_sample && <SampleTag />}
        </div>
        <div className="text-xs text-ink-3">{a.declared_employer || 'Employer not declared'}</div>
      </td>
      <td className="max-w-sm px-4 py-3.5">
        <StatusBadge status={a.status} size="sm" />
        {top && a.status !== 'processing' && <div className="mt-1.5 line-clamp-1 text-xs text-ink-2" title={top}>{top}</div>}
      </td>
      <td className="px-4 py-3.5"><Income a={a} /></td>
      <td className={`num px-4 py-3.5 text-right text-sm ${foirTone(a.foir)}`}>{pct(a.foir)}</td>
      <td className="px-4 py-3.5"><Score score={a.authenticity_score} /></td>
      <td className="px-4 py-3.5"><DocsProgress a={a} /></td>
      <td className="whitespace-nowrap py-3.5 pl-4 pr-5 text-right text-xs text-ink-3">{timeAgo(a.created_at)}</td>
    </tr>
  )
}

function MobileCard({ a }) {
  const top = uniqueReasons(a)[0]
  return (
    <Link to={`/applications/${a.id}`} className="block rounded-lg border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-medium text-ink">{a.applicant_name}</div>
          <div className="truncate text-xs text-ink-3">{a.declared_employer || 'Employer not declared'}</div>
        </div>
        <StatusBadge status={a.status} size="sm" />
      </div>
      {top && a.status !== 'processing' && <p className="mt-2 line-clamp-2 text-xs text-ink-2">{top}</p>}
      <div className="mt-3 grid grid-cols-3 gap-3 border-t border-line pt-3 text-xs">
        <div><div className="mb-0.5 text-ink-3">Income</div><Income a={a} align="left" /></div>
        <div><div className="mb-0.5 text-ink-3">FOIR</div><div className={`num text-sm font-medium ${foirTone(a.foir)}`}>{pct(a.foir)}</div></div>
        <div><div className="mb-0.5 text-ink-3">Authenticity</div><div className={`num text-sm font-semibold ${TONES[scoreTone(a.authenticity_score)].text}`}>{a.authenticity_score ?? '–'}</div></div>
      </div>
    </Link>
  )
}

function Queue({ data }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const options = FILTERS.map(f => ({ ...f, count: f.value === 'all' ? data.length : data.filter(a => a.status === f.value).length }))
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return data.filter(a => (filter === 'all' || a.status === filter) && (!q || `${a.applicant_name} ${a.declared_employer}`.toLowerCase().includes(q)))
  }, [data, filter, query])

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 className="font-serif text-[1.7rem] text-ink">Applications</h2>
        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
          <Segmented options={options} value={filter} onChange={setFilter} size="sm" />
          <div className="relative sm:w-60">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search name or employer" aria-label="Search applications" className={`${inputBase} w-full py-1.5 pl-9`} />
          </div>
        </div>
      </div>
      {shown.length === 0 ? (
        <EmptyState icon={Users} title="No applications match">Try another filter, or clear the search.</EmptyState>
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-lg border border-line bg-surface md:block">
            <table className="w-full text-left">
              <thead className="text-xs font-medium text-ink-3">
                <tr>
                  <th className="py-2.5 pl-5 pr-4 font-medium">Applicant</th>
                  <th className="px-4 py-2.5 font-medium">Verdict</th>
                  <th className="px-4 py-2.5 text-right font-medium">Verified income a month</th>
                  <th className="px-4 py-2.5 text-right font-medium">FOIR</th>
                  <th className="px-4 py-2.5 font-medium">Authenticity</th>
                  <th className="px-4 py-2.5 font-medium">Documents</th>
                  <th className="py-2.5 pl-4 pr-5 text-right font-medium">Created</th>
                </tr>
              </thead>
              <tbody>{shown.map(a => <Row key={a.id} a={a} />)}</tbody>
            </table>
          </div>
          <div className="space-y-3 md:hidden">{shown.map(a => <MobileCard key={a.id} a={a} />)}</div>
        </>
      )}
    </section>
  )
}

export default function Applications() {
  const { data, error } = usePolling(async () => (await api.get('/applications')).data, list => list.some(a => a.status === 'processing'))
  const [headline, setHeadline] = useState(null)
  useEffect(() => { api.get('/stats').then(r => setHeadline(r.data.evals?.headline || [])).catch(() => setHeadline([])) }, [])

  if (error && !data) return <Alert title="Could not load applications">{errorMessage(error)}</Alert>

  return (
    <div className="space-y-16">
      <Hero headline={headline} />
      <SampleStrip />
      {!data ? <Skeleton className="h-72" /> : data.length > 0 && <Queue data={data} />}
    </div>
  )
}
