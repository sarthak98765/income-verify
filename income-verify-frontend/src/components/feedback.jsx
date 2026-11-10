import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Button, Modal } from '@/components/ui'

/** Toasts and a promise-based confirm dialog, available anywhere through hooks. */

const ToastContext = createContext(() => {})
const ConfirmContext = createContext(async () => false)

export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [dialog, setDialog] = useState(null)
  const nextId = useRef(0)

  const toast = useCallback((message, kind = 'success') => {
    const id = (nextId.current += 1)
    setToasts(list => [...list, { id, message, kind }])
    setTimeout(() => setToasts(list => list.filter(t => t.id !== id)), kind === 'error' ? 6000 : 3500)
  }, [])

  const confirm = useCallback(options => new Promise(resolve => setDialog({ ...options, resolve })), [])
  const close = answer => { dialog?.resolve(answer); setDialog(null) }

  return (
    <ToastContext.Provider value={toast}>
      <ConfirmContext.Provider value={confirm}>
        {children}
        <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4" aria-live="polite">
          {toasts.map(t => (
            <div key={t.id} className="pointer-events-auto flex max-w-md items-start gap-2.5 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink shadow-pop animate-pop-in">
              {t.kind === 'error' ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-bad" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" />}
              <span>{t.message}</span>
            </div>
          ))}
        </div>
        <Modal
          open={!!dialog}
          onClose={() => close(false)}
          title={dialog?.title}
          footer={(
            <>
              <Button variant="secondary" onClick={() => close(false)}>Cancel</Button>
              <Button variant={dialog?.danger ? 'danger-solid' : 'primary'} onClick={() => close(true)}>{dialog?.confirmLabel || 'Confirm'}</Button>
            </>
          )}
        >
          <p className="text-sm text-ink-2">{dialog?.message}</p>
        </Modal>
      </ConfirmContext.Provider>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
export const useConfirm = () => useContext(ConfirmContext)
