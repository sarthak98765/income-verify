import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileCheck2 } from 'lucide-react'
import { api, errorMessage } from '@/lib/api'
import { Alert, Button, Card, DropZone, Field, buttonClass, inputClass } from '@/components/ui'
import { useToast } from '@/components/feedback'

const EXPECTED = [
  'The last 3 payslips',
  'A bank statement covering 6 months, with the salary account',
  'Form 16 for the latest year (optional, but it checks annual income)',
]

export default function NewApplication() {
  const [form, setForm] = useState({ applicant_name: '', declared_employer: '', declared_monthly_income: '' })
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const toast = useToast()
  const set = key => e => setForm(f => ({ ...f, [key]: e.target.value }))

  // Create the application first, then upload. If the upload fails the application still exists,
  // so the reviewer lands on it and can add the files again there.
  const submit = async e => {
    e.preventDefault()
    setError('')
    if (!files.length) return setError('Add at least one document.')
    setBusy(true)
    let created = null
    try {
      created = (await api.post('/applications', form)).data
      const body = new FormData()
      files.forEach(f => body.append('files', f))
      await api.post(`/applications/${created.id}/documents`, body)
      toast('Documents uploaded. Reading them now.')
      navigate(`/applications/${created.id}`)
    } catch (err) {
      if (created) {
        toast(`Application created, but the upload failed: ${errorMessage(err)}`, 'error')
        navigate(`/applications/${created.id}`)
      } else {
        setError(errorMessage(err))
        setBusy(false)
      }
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-ink-3 hover:text-ink"><ArrowLeft className="h-4 w-4" />Applications</Link>
      <div>
        <h1 className="font-serif text-[2.4rem] leading-tight tracking-tight text-ink">New application</h1>
        <p className="mt-2 max-w-2xl text-[15px] text-ink-2">What the applicant told you, and their documents. The documents are checked against what was declared.</p>
      </div>
      <form onSubmit={submit} className="space-y-6">
        <Card title="Applicant">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Applicant name" required>
                <input className={inputClass} value={form.applicant_name} onChange={set('applicant_name')} placeholder="As printed on the payslip" required maxLength={120} autoFocus />
              </Field>
            </div>
            <Field label="Declared employer">
              <input className={inputClass} value={form.declared_employer} onChange={set('declared_employer')} placeholder="e.g. Acme Logistics Pvt Ltd" maxLength={160} />
            </Field>
            <Field label="Declared monthly income (₹)" hint="Net take-home per month">
              <input className={inputClass} value={form.declared_monthly_income} onChange={set('declared_monthly_income')} placeholder="45,000" inputMode="decimal" />
            </Field>
          </div>
        </Card>
        <Card title="Documents" subtitle="The type of each file is detected automatically.">
          <ul className="mb-4 space-y-1.5 text-sm text-ink-2">
            {EXPECTED.map(t => <li key={t} className="flex items-start gap-2"><FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />{t}</li>)}
          </ul>
          <DropZone files={files} onChange={setFiles} disabled={busy} />
        </Card>
        {error && <Alert>{error}</Alert>}
        <div className="flex justify-end gap-2">
          <Link to="/" className={buttonClass('ghost', 'lg')}>Cancel</Link>
          <Button type="submit" size="lg" busy={busy}>Verify income</Button>
        </div>
      </form>
    </div>
  )
}
