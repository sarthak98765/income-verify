import { api, errorMessage } from '@/lib/api'
import usePolling from '@/lib/usePolling'
import { seconds, usd } from '@/lib/format'
import { Alert, Card, PageLoader, TONES } from '@/components/ui'

const VERDICT_BARS = [
  ['verified', 'Verified', 'ok'],
  ['needs_review', 'Needs review', 'warn'],
  ['flagged', 'Flagged', 'bad'],
  ['approved', 'Approved', 'brand'],
]

function VerdictSplit({ apps }) {
  const total = VERDICT_BARS.reduce((sum, [key]) => sum + apps[key], 0)
  if (!total) return <p className="text-sm text-ink-3">No applications checked yet. Run a sample from the home page.</p>
  return (
    <div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full">
        {VERDICT_BARS.map(([key, , tone]) => apps[key] > 0 && <div key={key} className={TONES[tone].bar} style={{ width: `${(100 * apps[key]) / total}%` }} />)}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {VERDICT_BARS.map(([key, label, tone]) => (
          <li key={key} className="flex items-center gap-2 text-ink-2"><span className={`h-2 w-2 rounded-full ${TONES[tone].bar}`} />{label}<span className="num font-medium text-ink">{apps[key]}</span></li>
        ))}
      </ul>
    </div>
  )
}

function IssueCatches({ issues }) {
  return (
    <Card title="Planted issues, by type" subtitle="Each test applicant carries at most one. Caught means it did not come out verified.">
      <ul className="space-y-3">
        {issues.map(i => (
          <li key={i.issue} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5">
            <span className="text-sm text-ink">{i.issue}</span>
            <span className="num text-sm font-medium text-ink">{i.caught} of {i.planted}</span>
            <div className="col-span-2 flex gap-1">
              {Array.from({ length: i.planted }, (_, k) => <span key={k} className={`h-1.5 flex-1 rounded-full ${k < i.caught ? 'bg-ok' : 'bg-bad'}`} />)}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function History({ rows }) {
  return (
    <Card title="What changed from v1 to v2" subtitle="Each version scored on its own held-out set of 30 applicants." padded={false}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs text-ink-3">
            <tr><th className="px-5 py-2 font-medium">Version</th><th className="px-3 py-2 text-right font-medium">Wrongly flagged</th><th className="px-3 py-2 text-right font-medium">Straight-through</th><th className="px-3 py-2 text-right font-medium">Verdicts right</th><th className="px-5 py-2 font-medium">What happened</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.version} className={`border-t border-line align-top ${i === rows.length - 1 ? 'bg-brand-50' : ''}`}>
                <td className="px-5 py-2.5 font-medium text-ink">{r.version}</td>
                <td className={`num px-3 py-2.5 text-right ${r.false_alarms.startsWith('0') ? 'text-ink' : 'font-medium text-bad'}`}>{r.false_alarms}</td>
                <td className="num px-3 py-2.5 text-right text-ink">{r.straight_through}</td>
                <td className="num px-3 py-2.5 text-right text-ink">{r.verdicts}</td>
                <td className="max-w-md px-5 py-2.5 text-ink-2">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Ablations({ rows }) {
  return (
    <Card title="What each part is worth" subtitle="v1 test set (30 applicants), with one part of the pipeline swapped at a time." padded={false}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="text-left text-xs text-ink-3">
            <tr><th className="px-5 py-2 font-medium">Variant</th><th className="px-3 py-2 text-right font-medium">Issues caught</th><th className="px-3 py-2 text-right font-medium">Straight-through</th><th className="px-5 py-2 text-right font-medium">Cost per applicant</th></tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.variant} className={`border-t border-line ${r.current ? 'bg-brand-50' : ''}`}>
                <td className="px-5 py-2.5 text-ink">{r.variant}{r.current && <span className="ml-2 text-xs font-medium text-brand-600">in use</span>}</td>
                <td className={`num px-3 py-2.5 text-right ${r.caught !== '11/11' ? 'font-medium text-bad' : 'text-ink'}`}>{r.caught}</td>
                <td className={`num px-3 py-2.5 text-right ${parseFloat(r.straight_through) < 50 ? 'font-medium text-bad' : 'text-ink'}`}>{r.straight_through}</td>
                <td className="num px-5 py-2.5 text-right text-ink">{r.cost}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-5 py-3 text-xs leading-relaxed text-ink-3">
        The extraction model is not the bottleneck: all three score the same. Without OCR, every scan and phone photo is unreadable, so most clean files end up with a person.
      </p>
    </Card>
  )
}

export default function Stats() {
  const { data, error } = usePolling(async () => (await api.get('/stats')).data, () => false)
  if (error && !data) return <Alert title="Could not load the numbers">{errorMessage(error)}</Alert>
  if (!data) return <PageLoader />
  const a = data.applications
  const ev = data.evals || {}
  const live = [
    ['Documents read', data.documents.processed, `${data.documents.pages} pages${data.documents.failed ? `, ${data.documents.failed} failed` : ''}`],
    ['Applications checked', a.analysed, `of ${a.total} created`],
    ['Straight-through', a.straight_through_pct == null ? '–' : `${a.straight_through_pct}%`, 'verified with no corrections'],
    ['Average AI cost', usd(data.avg_cost_usd), 'per application'],
    ['Average time', seconds(data.avg_seconds), 'per application'],
  ]

  return (
    <div className="space-y-12">
      <header className="max-w-3xl">
        <h1 className="font-serif text-[2.6rem] leading-[1.1] tracking-tight text-ink">How well it works, measured</h1>
        <p className="mt-3 text-[17px] leading-relaxed text-ink-2">
          Scored against the true values on 30 synthetic applicants (150 documents), generated fresh after the last change and never used while building it. 11 of them have something planted, and 23 payslips are phone photos. Labelled <span className="num whitespace-nowrap font-medium text-ink">{ev.label}</span>.
        </p>
      </header>

      {ev.headline?.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-8 gap-y-8 border-y border-line py-8 lg:grid-cols-4">
          {ev.headline.map(h => (
            <div key={h.label}>
              <dd className="num font-serif text-5xl leading-none text-ink">{h.value}</dd>
              <dt className="mt-2 max-w-[14rem] text-sm leading-snug text-ink-2">{h.label}</dt>
            </div>
          ))}
        </dl>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {ev.issues?.length > 0 && <IssueCatches issues={ev.issues} />}
        <Card title="All metrics" subtitle="Fresh test set, v2." padded={false}>
          <table className="w-full text-sm">
            <tbody>
              {(ev.rows || []).map(r => (
                <tr key={r.metric} className="border-t border-line first:border-0">
                  <td className="px-5 py-2.5 text-ink-2">{r.metric}</td>
                  <td className="num px-5 py-2.5 text-right font-medium text-ink">{r.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      {ev.history?.length > 0 && <History rows={ev.history} />}
      {ev.ablations?.length > 0 && <Ablations rows={ev.ablations} />}

      {ev.external && (
        <section className="grid items-baseline gap-4 rounded-lg border border-line bg-surface px-6 py-6 sm:grid-cols-[auto_1fr] sm:gap-8">
          <div className="num font-serif text-5xl leading-none text-ink">{ev.external.value}</div>
          <div>
            <h2 className="text-[15px] font-semibold text-ink">Bank statements it was never built for</h2>
            <p className="mt-1 text-sm text-ink-2">{ev.external.label}. Of the few rows misread, 81% broke the balance check and were sent for review instead of slipping through.</p>
          </div>
        </section>
      )}

      <section>
        <h2 className="font-serif text-[1.7rem] text-ink">On this server</h2>
        <p className="mt-1 text-sm text-ink-3">Live counts from every application run here, including samples.</p>
        <dl className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3 lg:grid-cols-5">
          {live.map(([label, value, hint]) => (
            <div key={label} className="bg-surface px-5 py-4">
              <dt className="text-xs text-ink-3">{label}</dt>
              <dd className="num mt-1 font-serif text-[1.65rem] leading-tight text-ink">{value}</dd>
              <dd className="text-xs text-ink-3">{hint}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-5 rounded-lg border border-line bg-surface p-5">
          <h3 className="mb-3 text-sm font-medium text-ink">Verdicts so far</h3>
          <VerdictSplit apps={a} />
        </div>
      </section>
    </div>
  )
}
