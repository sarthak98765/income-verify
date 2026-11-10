import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock, FileText, Flag, Info, Loader2, ShieldCheck, UploadCloud, X, XCircle } from 'lucide-react'
import { fmtSize } from '@/lib/format'

/** A white sheet on the paper background. `title` is a plain sentence-case heading, no eyebrow. */
export function Card({ title, subtitle, actions, children, className = '', padded = true }) {
  return (
    <section className={`rounded-lg border border-line bg-surface ${padded ? 'p-5' : ''} ${className}`}>
      {(title || actions) && (
        <div className={`flex flex-wrap items-start justify-between gap-3 ${padded ? 'mb-4' : 'border-b border-line px-5 py-3.5'}`}>
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-ink-3">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

const BUTTON_VARIANTS = {
  primary: 'bg-ink text-canvas hover:bg-ink/85 disabled:opacity-40',
  accent: 'bg-brand-600 text-white hover:bg-brand-700 dark:text-canvas disabled:opacity-40',
  secondary: 'border border-line bg-surface text-ink hover:border-ink-3/50 hover:bg-subtle disabled:opacity-50',
  ghost: 'text-ink-2 hover:bg-subtle hover:text-ink disabled:opacity-40',
  'danger-solid': 'bg-bad text-white hover:bg-bad/90 disabled:opacity-50',
  success: 'bg-ok text-white hover:bg-ok/90 dark:text-canvas disabled:opacity-50',
}
const BUTTON_SIZES = { sm: 'h-8 px-2.5 text-xs', md: 'h-9 px-3.5 text-sm', lg: 'h-11 px-5 text-[15px]' }

export const buttonClass = (variant = 'primary', size = 'md') =>
  `inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]}`

export function Button({ children, variant = 'primary', size = 'md', busy = false, icon: Icon, className = '', type = 'button', ...props }) {
  return (
    <button type={type} className={`${buttonClass(variant, size)} ${className}`} disabled={busy || props.disabled} {...props}>
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon && <Icon className="h-4 w-4" />}
      {children}
    </button>
  )
}

export function Field({ label, children, hint, required }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block font-medium text-ink">{label}{required && <span className="text-bad"> *</span>}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-3">{hint}</span>}
    </label>
  )
}

export const inputBase = 'rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-subtle disabled:text-ink-3'
export const inputClass = `w-full ${inputBase}`

// ── Verdicts and statuses ─────────────────────────────────────────────────────

export const VERDICTS = {
  verified: { label: 'Verified', icon: ShieldCheck, tone: 'ok' },
  needs_review: { label: 'Needs review', icon: AlertTriangle, tone: 'warn' },
  flagged: { label: 'Flagged', icon: Flag, tone: 'bad' },
  approved: { label: 'Approved', icon: CheckCircle2, tone: 'brand' },
  processing: { label: 'Processing', icon: Loader2, tone: 'brand', spin: true },
  draft: { label: 'Draft', icon: FileText, tone: 'neutral' },
  failed: { label: 'Failed', icon: XCircle, tone: 'bad' },
  queued: { label: 'Queued', icon: Clock, tone: 'neutral' },
  completed: { label: 'Read', icon: CheckCircle2, tone: 'ok' },
}

export const TONES = {
  ok: { badge: 'bg-ok/10 text-ok ring-ok/25', text: 'text-ok', bar: 'bg-ok', soft: 'bg-ok/[0.07]', border: 'border-ok/40' },
  warn: { badge: 'bg-warn/10 text-warn ring-warn/30', text: 'text-warn', bar: 'bg-warn', soft: 'bg-warn/[0.07]', border: 'border-warn/40' },
  bad: { badge: 'bg-bad/10 text-bad ring-bad/25', text: 'text-bad', bar: 'bg-bad', soft: 'bg-bad/[0.06]', border: 'border-bad/40' },
  brand: { badge: 'bg-brand-600/10 text-brand-600 ring-brand-600/25', text: 'text-brand-600', bar: 'bg-brand-600', soft: 'bg-brand-50', border: 'border-brand-600/40' },
  neutral: { badge: 'bg-subtle text-ink-2 ring-line', text: 'text-ink-3', bar: 'bg-ink-3', soft: 'bg-subtle', border: 'border-line' },
}

export const scoreTone = s => (s == null ? 'neutral' : s >= 80 ? 'ok' : s >= 50 ? 'warn' : 'bad')

export function StatusBadge({ status, label, size = 'md' }) {
  const v = VERDICTS[status] || VERDICTS.draft
  const t = TONES[v.tone]
  const Icon = v.icon
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full font-medium ring-1 ring-inset ${t.badge} ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'}`}>
      <Icon className={`h-3.5 w-3.5 ${v.spin ? 'animate-spin' : ''}`} />
      {label || v.label}
    </span>
  )
}

// pass / warn / fail for a check
export const CHECK_STATUS = {
  pass: { icon: CheckCircle2, className: 'text-ok', label: 'Pass' },
  warn: { icon: AlertTriangle, className: 'text-warn', label: 'Warning' },
  fail: { icon: XCircle, className: 'text-bad', label: 'Fail' },
}

export function CheckIcon({ status, className = 'h-4 w-4' }) {
  const s = CHECK_STATUS[status] || CHECK_STATUS.warn
  return <s.icon className={`${className} shrink-0 ${s.className}`} aria-label={s.label} />
}

// ── Feedback blocks ───────────────────────────────────────────────────────────

const ALERTS = {
  error: { icon: XCircle, className: 'border-bad/30 bg-bad/[0.06] text-ink', iconClass: 'text-bad' },
  warning: { icon: AlertTriangle, className: 'border-warn/30 bg-warn/[0.07] text-ink', iconClass: 'text-warn' },
  info: { icon: Info, className: 'border-brand-600/25 bg-brand-50 text-ink', iconClass: 'text-brand-600' },
}

export function Alert({ kind = 'error', title, children, action }) {
  const a = ALERTS[kind]
  return (
    <div className={`flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${a.className}`} role={kind === 'error' ? 'alert' : 'status'}>
      <a.icon className={`mt-0.5 h-4 w-4 shrink-0 ${a.iconClass}`} />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={title ? 'mt-0.5 text-ink-2' : ''}>{children}</div>}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({ icon: Icon = FileText, title, children, action }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed border-line bg-surface px-6 py-14 text-center">
      <Icon className="h-7 w-7 text-ink-3" />
      <h3 className="mt-3 font-serif text-xl text-ink">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-ink-3">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-md bg-line/60 ${className}`} />
}

export function PageLoader() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Skeleton className="h-9 w-72" />
      <Skeleton className="h-40" />
      <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-48 md:col-span-2" /><Skeleton className="h-48" /></div>
    </div>
  )
}

export function ProgressBar({ value, max = 100, tone = 'brand', className = 'h-1.5' }) {
  const width = Math.max(0, Math.min(100, (100 * (value || 0)) / (max || 1)))
  return (
    <div className={`overflow-hidden rounded-full bg-line ${className}`}>
      <div className={`h-full rounded-full transition-all duration-500 ${TONES[tone].bar}`} style={{ width: `${width}%` }} />
    </div>
  )
}

/** A row of mutually exclusive options, like a segmented control. */
export function Segmented({ options, value, onChange, size = 'md' }) {
  return (
    <div className="scroll-thin flex max-w-full overflow-x-auto rounded-md border border-line bg-surface p-0.5" role="radiogroup">
      {options.map(o => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[5px] font-medium transition ${size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'} ${value === o.value ? 'bg-ink text-canvas' : 'text-ink-2 hover:bg-subtle hover:text-ink'}`}
        >
          {o.dot && <span className={`h-2 w-2 rounded-full ${TONES[o.dot].bar}`} />}
          {o.label}
          {o.count != null && <span className={`num ${value === o.value ? 'opacity-70' : 'text-ink-3'}`}>{o.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Modal({ open, onClose, title, subtitle, children, footer, width = 'max-w-lg' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = e => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-0 backdrop-blur-[2px] animate-fade-in sm:items-center sm:p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`flex max-h-[92vh] w-full ${width} flex-col rounded-t-xl border border-line bg-surface shadow-pop animate-pop-in sm:rounded-xl`}>
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 className="font-serif text-xl text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 text-sm text-ink-3">{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-ink-3 hover:bg-subtle hover:text-ink" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="scroll-thin overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp'

export function DropZone({ files, onChange, max = 10, disabled = false }) {
  const [over, setOver] = useState(false)
  const input = useRef(null)
  const add = list => {
    const picked = [...list].filter(f => /\.(pdf|png|jpe?g|webp)$/i.test(f.name))
    const names = new Set(files.map(f => f.name + f.size))
    onChange([...files, ...picked.filter(f => !names.has(f.name + f.size))].slice(0, max))
  }
  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && input.current?.click()}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        onDragOver={e => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); if (!disabled) add(e.dataTransfer.files) }}
        className={`flex cursor-pointer flex-col items-center rounded-lg border border-dashed px-6 py-9 text-center transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${over ? 'border-brand-600 bg-brand-50' : 'border-ink-3/40 bg-subtle/50 hover:border-brand-600 hover:bg-brand-50'} ${disabled ? 'pointer-events-none opacity-60' : ''}`}
      >
        <UploadCloud className="h-7 w-7 text-brand-600" />
        <div className="mt-2 text-sm font-medium text-ink">Drop files here, or click to choose</div>
        <div className="mt-1 text-xs text-ink-3">PDF, PNG, JPG or WEBP, up to 15 MB and 30 pages each, {max} files at a time</div>
        <input ref={input} type="file" multiple accept={ACCEPT} className="hidden" onChange={e => { add(e.target.files); e.target.value = '' }} />
      </div>
      {files.length > 0 && (
        <ul className="mt-3 divide-y divide-line rounded-md border border-line">
          {files.map((f, i) => (
            <li key={f.name + f.size} className="flex items-center gap-3 px-3 py-2 text-sm">
              <FileText className="h-4 w-4 shrink-0 text-ink-3" />
              <span className="min-w-0 flex-1 truncate text-ink">{f.name}</span>
              <span className="num text-xs text-ink-3">{fmtSize(f.size)}</span>
              {!disabled && (
                <button type="button" onClick={() => onChange(files.filter((_, j) => j !== i))} className="rounded p-0.5 text-ink-3 hover:bg-subtle hover:text-bad" aria-label={`Remove ${f.name}`}>
                  <X className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
