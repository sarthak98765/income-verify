import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, BadgeCheck, FilePlus2, FileSpreadsheet, FileJson, Loader2, RotateCcw, Trash2, Upload } from 'lucide-react'
import { api, errorMessage, exportUrl } from '@/lib/api'
import usePolling from '@/lib/usePolling'
import { fmtDate, rupees } from '@/lib/format'
import { isActive } from '@/lib/progress'
import { BankBehaviour, ChecksList, DecisionSheet, DocumentsList, LiveRun, RunDetails, SalaryMatches, UnderwriterNote } from '@/components/ApplicationParts'
import { Alert, Button, DropZone, EmptyState, Modal, PageLoader, buttonClass } from '@/components/ui'
import { useConfirm, useToast } from '@/components/feedback'

const ANALYSED = ['verified', 'needs_review', 'flagged', 'approved']

function AddDocuments({ app, open, onClose, onAdded }) {
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const toast = useToast()
  const upload = async () => {
    setBusy(true)
    setError('')
    try {
      const body = new FormData()
      files.forEach(f => body.append('files', f))
      await api.post(`/applications/${app.id}/documents`, body)
      toast(`${files.length} document${files.length === 1 ? '' : 's'} added. The application will be analysed again.`)
      setFiles([])
      onAdded()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add documents"
      subtitle="They are read like the others, then the whole application is checked again."
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button busy={busy} disabled={!files.length} onClick={upload}>Add {files.length || ''} document{files.length === 1 ? '' : 's'}</Button></>}
    >
      <DropZone files={files} onChange={setFiles} disabled={busy} />
      {error && <div className="mt-3"><Alert>{error}</Alert></div>}
    </Modal>
  )
}

function Export({ app }) {
  return (
    <div className="flex">
      <a href={exportUrl(app.id, 'xlsx')} className={`${buttonClass('secondary')} rounded-r-none`} title="Excel workbook: summary, checks, salary matches, transactions"><FileSpreadsheet className="h-4 w-4" />Excel</a>
      <a href={exportUrl(app.id, 'json')} className={`${buttonClass('secondary')} -ml-px rounded-l-none`} title="Everything as JSON, for a loan system"><FileJson className="h-4 w-4" />JSON</a>
    </div>
  )
}

export default function ApplicationDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState('')
  const { data: app, error, reload, setData } = usePolling(
    async () => (await api.get(`/applications/${id}`)).data,
    a => a.status === 'processing' || a.documents.some(d => isActive(d.status)),
  )

  if (error && !app) {
    return error.response?.status === 404
      ? <EmptyState title="Application not found" action={<Link to="/" className={buttonClass()}>Back to applications</Link>}>It may have been deleted. Uploads are removed after 24 hours.</EmptyState>
      : <Alert title="Could not load the application">{errorMessage(error)}</Alert>
  }
  if (!app) return <PageLoader />

  const act = async (name, request, message) => {
    setBusy(name)
    try {
      const { data } = await request()
      if (data?.id) setData(a => ({ ...a, ...data }))
      toast(message)
      reload()
    } catch (err) {
      toast(errorMessage(err), 'error')
    } finally {
      setBusy('')
    }
  }

  const approve = async () => {
    const flagged = app.status === 'flagged'
    const ok = await confirm({
      title: flagged ? 'Approve a flagged application?' : 'Approve this application?',
      message: flagged ? 'The checks flagged this applicant. Approve only if you have checked every finding against the originals.' : 'This is the final sign-off. Fields can no longer be edited afterwards.',
      confirmLabel: 'Approve',
      danger: flagged,
    })
    if (ok) act('approve', () => api.post(`/applications/${app.id}/approve`), 'Application approved.')
  }

  const remove = async () => {
    const ok = await confirm({ title: 'Delete this application?', message: `This permanently deletes ${app.applicant_name}'s application and its ${app.documents.length} documents.`, confirmLabel: 'Delete', danger: true })
    if (!ok) return
    try {
      await api.delete(`/applications/${app.id}`)
      toast('Application deleted.')
      navigate('/')
    } catch (err) {
      toast(errorMessage(err), 'error')
    }
  }

  const working = app.status === 'processing' || app.documents.some(d => isActive(d.status))
  const analysed = ANALYSED.includes(app.status)
  const failedDocs = app.documents.filter(d => d.status === 'failed')
  const firstRun = working && !app.analyzed_at

  return (
    <div className="space-y-6">
      <AddDocuments app={app} open={adding} onClose={() => setAdding(false)} onAdded={reload} />
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />Applications</Link>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-serif text-[2.4rem] leading-tight tracking-tight text-ink">{app.applicant_name}</h1>
            {app.is_sample && <span className="rounded border border-line px-1.5 py-px text-xs font-medium text-ink-3">Synthetic sample</span>}
          </div>
          <p className="mt-1 text-sm text-ink-2">
            {app.declared_employer || 'Employer not declared'}
            <span className="text-ink-3">{app.declared_monthly_income ? `, declared ${rupees(app.declared_monthly_income)} a month` : ', no income declared'}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {app.status !== 'approved' && <Button variant="secondary" icon={FilePlus2} onClick={() => setAdding(true)} disabled={working}>Add documents</Button>}
          {(app.status === 'failed' || analysed) && app.status !== 'approved' && app.documents.length > 0 && (
            <Button variant="secondary" icon={RotateCcw} busy={busy === 'analyze'} disabled={working} onClick={() => act('analyze', () => api.post(`/applications/${app.id}/analyze`), 'Checking the application again.')}>Re-check</Button>
          )}
          {analysed && <Export app={app} />}
          {analysed && app.status !== 'approved' && <Button variant={app.status === 'verified' ? 'success' : 'secondary'} icon={BadgeCheck} busy={busy === 'approve'} disabled={working} onClick={approve}>Approve</Button>}
          <Button variant="ghost" icon={Trash2} onClick={remove} aria-label="Delete application" title="Delete application" />
        </div>
      </div>

      {app.status === 'failed' && <Alert title="Processing failed">{app.error || 'Something went wrong while checking the documents. Use Re-check to try again.'}</Alert>}
      {failedDocs.length > 0 && !working && (
        <Alert kind="warning" title={`${failedDocs.length} document${failedDocs.length === 1 ? '' : 's'} could not be read`}>
          {failedDocs.map(d => `${d.filename}: ${d.error || 'unknown error'}`).join('. ')}
        </Alert>
      )}

      {app.status === 'draft' && app.documents.length === 0 && (
        <EmptyState icon={Upload} title="No documents yet" action={<Button icon={FilePlus2} onClick={() => setAdding(true)}>Add documents</Button>}>
          Add the last 3 payslips, a 6-month bank statement and Form 16 to start.
        </EmptyState>
      )}

      {firstRun && <LiveRun app={app} />}
      {working && !firstRun && (
        <div className="flex items-center gap-3 rounded-md border border-brand-600/25 bg-brand-50 px-4 py-3 text-sm text-ink">
          <Loader2 className="h-4 w-4 animate-spin text-brand-600" />Checking again with the latest values. The verdict below updates when it finishes.
        </div>
      )}

      {analysed && (
        <div className={`space-y-6 transition-opacity ${working ? 'opacity-50' : ''}`}>
          <DecisionSheet app={app} />
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <SalaryMatches matches={app.salary_matches} />
              <ChecksList app={app} />
              <BankBehaviour app={app} />
            </div>
            <div className="space-y-6">
              <UnderwriterNote app={app} />
              <DocumentsList documents={app.documents} />
              <RunDetails app={app} />
            </div>
          </div>
        </div>
      )}

      {!analysed && !firstRun && app.documents.length > 0 && <DocumentsList documents={app.documents} />}
      <p className="text-xs text-ink-3">Created {fmtDate(app.created_at)}</p>
    </div>
  )
}
