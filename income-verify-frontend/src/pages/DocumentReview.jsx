import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Crosshair, Eye, EyeOff, History, PencilLine, RotateCcw } from 'lucide-react'
import { api, errorMessage, fileUrl } from '@/lib/api'
import usePolling from '@/lib/usePolling'
import { DOC_TYPES, amount, fmtDate, fmtMonth, humanize, mask, rupees } from '@/lib/format'
import { LAYOUTS, doubtsFor, getAt, toInput } from '@/lib/fields'
import { docLabel } from '@/lib/findings'
import { isActive, stageText } from '@/lib/progress'
import { ImageViewer, PdfViewer } from '@/components/DocViewer'
import { Alert, Button, Card, CheckIcon, EmptyState, PageLoader, Segmented, buttonClass, inputBase } from '@/components/ui'
import { useToast } from '@/components/feedback'

const siblingLabel = s => {
  if (s.status !== 'completed') return s.filename
  const month = s.filename.match(/\d{4}-\d{2}/)?.[0]
  return s.doc_type === 'payslip' && month ? `Payslip ${fmtMonth(month)}` : DOC_TYPES[s.doc_type] || s.filename
}

// Identity numbers are masked on screen; the reviewer can reveal them.
const MASKED = new Set(['pan', 'employee_pan', 'account.account_number', 'bank_account'])

/** What the viewer should look for when a field or row is selected. */
function targetFor(doc, path) {
  const row = path.match(/^transactions\.(\d+)/)
  if (row) {
    const t = doc.fields.transactions?.[Number(row[1])]
    if (!t) return null
    return { value: t.balance, numeric: true, row: true, page: t.page || null, tone: doubtsFor(doc, `transactions.${t.row ?? row[1]}`).length ? 'warn' : null, path }
  }
  const v = getAt(doc.fields, path)
  if (v == null || v === '') return null
  return { value: v, numeric: typeof v === 'number', page: doc.fields?.page || null, tone: doubtsFor(doc, path).length ? 'warn' : null, path }
}

function FieldRow({ doc, path, label, money, edits, setEdit, editing, onLocate, active }) {
  const [reveal, setReveal] = useState(false)
  const ref = useRef(null)
  useEffect(() => { if (active) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [active])
  const original = getAt(doc.fields, path)
  if (original === undefined) return null
  const value = edits[path] ?? toInput(original)
  const changed = edits[path] !== undefined && edits[path] !== toInput(original)
  const doubts = doubtsFor(doc, path)
  const masked = MASKED.has(path) && !reveal && !editing
  const shown = original == null || original === '' ? <span className="text-ink-3">Not found</span> : money ? rupees(original, true) : masked ? mask(original) : String(original)
  return (
    <div ref={ref} className={`scroll-mt-24 py-2 pl-3 pr-1 ${doubts.length ? 'bg-warn/[0.07] shadow-[inset_2px_0_0_rgb(var(--warn))]' : active ? 'bg-brand-50 shadow-[inset_2px_0_0_rgb(var(--brand-600))]' : ''}`}>
      <div className="flex items-center gap-3">
        <label htmlFor={path} className="w-36 shrink-0 text-sm text-ink-3">{label}</label>
        {editing ? (
          <input id={path} value={value} onChange={e => setEdit(path, e.target.value)} inputMode={money ? 'decimal' : undefined} className={`${inputBase} min-w-0 flex-1 py-1 ${money ? 'num text-right' : ''} ${changed ? '!border-brand-600 ring-2 ring-brand-600/15' : ''}`} />
        ) : (
          <button type="button" onClick={() => onLocate(path)} className={`group flex min-w-0 flex-1 items-center gap-2 rounded text-left text-sm font-medium text-ink ${money ? 'justify-end' : ''}`} title="Show on the page">
            <span className={`truncate ${money ? 'num' : ''}`}>{shown}</span>
            <Crosshair className="h-3.5 w-3.5 shrink-0 text-ink-3 opacity-0 transition group-hover:opacity-100" />
          </button>
        )}
        {MASKED.has(path) && !editing && original && (
          <button type="button" onClick={() => setReveal(r => !r)} className="shrink-0 rounded p-1 text-ink-3 hover:bg-subtle hover:text-ink" aria-label={reveal ? `Hide ${label}` : `Show ${label}`}>{reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}</button>
        )}
      </div>
      {changed && <div className="num mt-1 text-right text-xs text-ink-3">was {money ? rupees(original, true) : String(original ?? '–')}</div>}
      {doubts.map(d => <p key={d} className="mt-1 flex gap-1.5 text-xs text-ink-2"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-warn" />{d}</p>)}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <h3 className="mb-1 text-sm font-medium text-ink">{title}</h3>
      <div className="divide-y divide-line/70">{children}</div>
    </div>
  )
}

const CELL = `${inputBase} w-full !px-1.5 !py-0.5 !text-xs`

function Transactions({ doc, edits, setEdit, editing, onLocate, focus }) {
  const rows = doc.fields.transactions || []
  const doubted = useMemo(() => new Set(rows.map((t, i) => (doubtsFor(doc, `transactions.${t.row ?? i}`).length ? i : null)).filter(i => i != null)), [doc, rows])
  const [only, setOnly] = useState(doubted.size > 0 ? 'review' : 'all')
  const activeRow = focus?.match(/^transactions\.(\d+)/) ? Number(focus.split('.')[1]) : null
  const activeRef = useRef(null)
  useEffect(() => { activeRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [activeRow])
  const shown = rows.map((t, i) => [t, i]).filter(([, i]) => only === 'all' || doubted.has(i))
  const cell = (i, key, money) => {
    const path = `transactions.${i}.${key}`
    const original = rows[i][key]
    const changed = edits[path] !== undefined && edits[path] !== toInput(original)
    if (!editing) return <span className={money ? 'num' : ''}>{money ? amount(original) : original}</span>
    return <input aria-label={`${key}, row ${i + 1}`} value={edits[path] ?? toInput(original)} onChange={e => setEdit(path, e.target.value)} className={`${CELL} ${money ? 'num text-right' : ''} ${changed ? '!border-brand-600' : ''}`} />
  }
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-ink">Transactions</h3>
        <Segmented size="sm" value={only} onChange={setOnly} options={[{ value: 'review', label: 'To confirm', count: doubted.size, dot: doubted.size ? 'warn' : undefined }, { value: 'all', label: 'All', count: rows.length }]} />
      </div>
      {shown.length === 0 ? <p className="rounded-md bg-subtle px-3 py-2.5 text-sm text-ink-2">Every row adds up with the running balance.</p> : (
        <div className="scroll-thin max-h-[56vh] overflow-auto rounded-md border border-line">
          <table className="w-full table-fixed text-xs">
            <thead className="sticky top-0 z-10 bg-surface text-left text-ink-3 shadow-[0_1px_0_rgb(var(--line))]">
              <tr><th className="w-[5.4rem] px-2 py-2 font-medium">Date</th><th className="px-2 py-2 font-medium">Narration</th><th className="w-[5rem] px-2 py-2 text-right font-medium">Debit</th><th className="w-[5rem] px-2 py-2 text-right font-medium">Credit</th><th className="w-[6rem] px-2 py-2 text-right font-medium">Balance</th></tr>
            </thead>
            <tbody>
              {shown.map(([t, i]) => {
                const doubts = doubtsFor(doc, `transactions.${t.row ?? i}`)
                const active = activeRow === i
                return (
                  <tr
                    key={i}
                    ref={active ? activeRef : null}
                    onClick={() => !editing && onLocate(`transactions.${i}`)}
                    className={`border-t border-line align-top ${editing ? '' : 'cursor-pointer hover:bg-subtle'} ${doubts.length ? 'bg-warn/[0.08]' : ''} ${active ? 'outline outline-2 -outline-offset-2 outline-brand-600' : ''}`}
                    title={doubts.join('\n') || 'Show on the page'}
                  >
                    <td className="num whitespace-nowrap px-2 py-1.5 text-ink-2">{cell(i, 'date')}</td>
                    <td className="min-w-0 px-2 py-1.5">
                      <div className={editing ? '' : 'truncate text-ink'}>{cell(i, 'description')}</div>
                      {!editing && t.category && <div className="text-[11px] text-ink-3">{humanize(t.category)}</div>}
                    </td>
                    <td className="px-2 py-1.5 text-right text-ink">{cell(i, 'debit', true)}</td>
                    <td className="px-2 py-1.5 text-right text-ok">{cell(i, 'credit', true)}</td>
                    <td className="px-2 py-1.5 text-right font-medium text-ink">{cell(i, 'balance', true)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {doubted.size > 0 && <p className="mt-2 text-xs text-ink-3">Shaded rows break the running balance. Click one to see it on the page, and correct the value that was misread.</p>}
    </div>
  )
}

function DocChecks({ doc, onPage }) {
  const checks = [...(doc.checks || [])].sort((a, b) => (a.status === 'pass') - (b.status === 'pass'))
  const signals = doc.signals || []
  if (!checks.length && !signals.length) return null
  return (
    <Card title="Checks on this document">
      <ul className="space-y-2.5">
        {signals.map((s, i) => (
          <li key={`s-${i}`} className="flex gap-2.5 text-sm">
            <span className="num w-8 shrink-0 text-right text-xs font-semibold text-bad">−{s.weight}</span>
            <span className="min-w-0 flex-1 text-ink">{s.message}</span>
            {s.page && <button type="button" onClick={() => onPage(s.page)} className="shrink-0 text-xs text-brand-600 hover:underline">page {s.page}</button>}
          </li>
        ))}
        {checks.map((c, i) => (
          <li key={`${c.key}-${i}`} className="flex gap-2.5 text-sm">
            <span className="flex w-8 shrink-0 justify-end"><CheckIcon status={c.status} className="mt-0.5 h-4 w-4" /></span>
            <span className={`min-w-0 flex-1 ${c.status === 'pass' ? 'text-ink-2' : 'text-ink'}`}>{c.message}</span>
            {c.page && <button type="button" onClick={() => onPage(c.page)} className="shrink-0 text-xs text-brand-600 hover:underline">page {c.page}</button>}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function EditHistory({ edits }) {
  if (!edits?.length) return null
  return (
    <Card title="Corrections" actions={<History className="h-4 w-4 text-ink-3" />}>
      <ul className="space-y-2 text-sm">
        {edits.map((e, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-ink">{humanize(e.field_path.replace(/^transactions\.(\d+)\./, (_, n) => `row ${Number(n) + 1} `))}</span>
            <span className="num text-ink-3 line-through">{typeof e.old_value === 'number' ? amount(e.old_value) : String(e.old_value ?? '–')}</span>
            <span className="num text-ink">{typeof e.new_value === 'number' ? amount(e.new_value) : String(e.new_value ?? '–')}</span>
            <span className="ml-auto text-xs text-ink-3">{fmtDate(e.created_at)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function DocumentReview() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [edits, setEdits] = useState({})
  const [editing, setEditing] = useState(false)
  const [page, setPage] = useState(null)
  const [focus, setFocus] = useState(null)
  const [saving, setSaving] = useState(false)
  const { data: doc, error } = usePolling(async () => (await api.get(`/documents/${id}`)).data, d => isActive(d.status))

  // A new document: clean edits, and the page / value the link pointed to.
  const [loadedId, setLoadedId] = useState(null)
  if (loadedId !== id) {
    setLoadedId(id); setEdits({}); setEditing(false)
    setPage(params.get('page') ? Number(params.get('page')) : null)
    setFocus(params.get('focus'))
  }

  const target = useMemo(() => (doc && doc.id === id && focus && doc.fields ? targetFor(doc, focus) : null), [doc, id, focus])

  if (error && !doc) {
    return error.response?.status === 404
      ? <EmptyState title="Document not found" action={<Link to="/" className={buttonClass()}>Back to applications</Link>}>It may have been deleted with its application.</EmptyState>
      : <Alert title="Could not load the document">{errorMessage(error)}</Alert>
  }
  if (!doc || doc.id !== id) return <PageLoader />

  const layout = LAYOUTS[doc.doc_type]
  const locked = doc.status !== 'completed' || ['approved', 'processing'].includes(doc.application.status)
  const changed = Object.entries(edits).filter(([path, v]) => v !== toInput(getAt(doc.fields, path)))
  const setEdit = (path, value) => setEdits(e => ({ ...e, [path]: value }))
  const currentPage = page ?? target?.page ?? doc.fields?.page ?? 1
  const locate = path => {
    const t = targetFor(doc, path)
    setFocus(path)
    if (t?.page) setPage(t.page)
  }
  const shared = { doc, edits, setEdit, editing, onLocate: locate, focus }

  const save = async () => {
    setSaving(true)
    try {
      const { data } = await api.patch(`/documents/${doc.id}/fields`, { edits: changed.map(([path, value]) => ({ path, value })) })
      toast(data.changed ? `Saved ${data.changed} correction${data.changed === 1 ? '' : 's'}. Checking the application again.` : 'Nothing changed.')
      if (data.changed) navigate(`/applications/${doc.application.id}`)
    } catch (err) {
      toast(errorMessage(err), 'error')
    } finally {
      setSaving(false)
    }
  }
  const cancelEdit = () => { setEdits({}); setEditing(false) }

  const notes = [
    `${doc.pages} page${doc.pages === 1 ? '' : 's'}`,
    doc.classified_by && `type found by ${doc.classified_by === 'rules' ? 'keyword rules' : 'a model'}`,
    doc.low_quality_pages?.length > 0 && `page ${doc.low_quality_pages.join(', ')} re-read as an image`,
    doc.reread?.reread_rows > 0 && `${doc.reread.reread_rows} rows re-read by a second model, ${doc.reread.fixed} corrected`,
    doc.reread?.image_reread && (doc.reread.fixed ? 'totals the OCR missed were read from the image by a second model' : 'a second read from the image could not settle the totals'),
  ].filter(Boolean)

  return (
    <div className="space-y-5">
      <Link to={`/applications/${doc.application.id}`} className="inline-flex items-center gap-1.5 text-sm text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />{doc.application.applicant_name}</Link>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-serif text-[2.1rem] leading-tight tracking-tight text-ink">{doc.status === 'completed' ? docLabel(doc) : doc.filename}</h1>
          <p className="mt-1 text-sm text-ink-3">{doc.filename}, {notes.join(', ')}</p>
        </div>
        {doc.siblings?.length > 1 && (
          <nav className="scroll-thin flex max-w-full gap-1 overflow-x-auto rounded-md border border-line bg-surface p-0.5" aria-label="Documents in this application">
            {doc.siblings.map(s => (
              <Link key={s.id} to={`/documents/${s.id}`} className={`shrink-0 whitespace-nowrap rounded-[5px] px-2.5 py-1 text-xs font-medium ${s.id === doc.id ? 'bg-ink text-canvas' : 'text-ink-2 hover:bg-subtle hover:text-ink'}`}>
                {siblingLabel(s)}
              </Link>
            ))}
          </nav>
        )}
      </div>

      {doc.status === 'failed' && <Alert title="This document could not be read">{doc.error}</Alert>}
      {isActive(doc.status) && <Alert kind="info" title="Still reading this document">{stageText(doc.progress?.stage || doc.status)}. The values appear here when it is done.</Alert>}

      <div className="grid gap-5 lg:grid-cols-12">
        <div className="h-[70vh] overflow-hidden rounded-lg border border-line bg-surface lg:sticky lg:top-[5.5rem] lg:col-span-7 lg:h-[calc(100vh-7.5rem)]">
          {doc.mime?.startsWith('image/')
            ? <ImageViewer url={fileUrl(doc.id)} filename={doc.filename} />
            : <PdfViewer url={fileUrl(doc.id)} page={currentPage} onPage={setPage} target={target} filename={doc.filename} />}
        </div>

        <div className="space-y-5 lg:col-span-5">
          {doc.status === 'completed' && !layout && (
            <Alert kind="warning" title="Not a document type we check">This file was not recognised as a payslip, bank statement or Form 16, so it is not used in the analysis.</Alert>
          )}
          {layout && doc.status === 'completed' && (
            <section className="rounded-lg border border-line bg-surface">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-3.5">
                <div>
                  <h2 className="text-[15px] font-semibold text-ink">What was read</h2>
                  <p className="mt-0.5 text-sm text-ink-3">{editing ? 'Correct any value that was misread, then save.' : 'Copied as printed. Click a value to see it on the page.'}</p>
                </div>
                {!locked && !editing && <Button variant="secondary" size="sm" icon={PencilLine} onClick={() => setEditing(true)}>Correct values</Button>}
              </div>
              <div className="space-y-5 px-4 py-4">
                {layout.sections.map(s => (
                  <Section key={s.title} title={s.title}>{s.fields.map(([path, label]) => <FieldRow key={path} path={path} label={label} active={focus === path} {...shared} />)}</Section>
                ))}
                {(layout.lines || []).map(([path, title]) => {
                  const lines = getAt(doc.fields, path) || []
                  if (!lines.length) return null
                  return <Section key={path} title={title}>{lines.map((line, i) => <FieldRow key={i} path={`${path}.${i}.amount`} label={line.name} money active={focus === `${path}.${i}.amount`} {...shared} />)}</Section>
                })}
                <Section title="Totals">{layout.totals.map(([path, label]) => <FieldRow key={path} path={path} label={label} money active={focus === path} {...shared} />)}</Section>
                {layout.transactions && <Transactions {...shared} />}
              </div>
              {editing && (
                <div className="sticky bottom-0 flex items-center justify-between gap-3 rounded-b-lg border-t border-line bg-surface/95 px-5 py-3 backdrop-blur">
                  <span className="text-sm text-ink-2">{changed.length ? `${changed.length} correction${changed.length === 1 ? '' : 's'}` : 'No corrections yet'}</span>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" icon={RotateCcw} onClick={cancelEdit}>Cancel</Button>
                    <Button size="sm" busy={saving} disabled={!changed.length} onClick={save}>Save and re-check</Button>
                  </div>
                </div>
              )}
            </section>
          )}
          {locked && doc.status === 'completed' && <p className="text-xs text-ink-3">{doc.application.status === 'approved' ? 'The application is approved, so values are locked.' : 'The application is being checked. Corrections open again when it finishes.'}</p>}
          <DocChecks doc={doc} onPage={p => { setFocus(null); setPage(p) }} />
          <EditHistory edits={doc.edits} />
        </div>
      </div>
    </div>
  )
}
