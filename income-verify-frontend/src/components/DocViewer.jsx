import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink, Minus, Plus, ScanLine } from 'lucide-react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

/**
 * The original document, rendered the same in every browser (pdf.js), with an optional highlight.
 * `target` = { value, numeric, row, tone }: the viewer looks for that value in the page's text layer
 * and boxes it (or the whole line when `row`). Scans and photos have no text layer, so for them it can
 * only open the right page.
 */

const clean = s => s.toLowerCase().replace(/[\s,₹]|rs\.?/g, '')
const asNumber = s => {
  const t = s.replace(/\b(cr|dr)\.?\s*$/i, '').replace(/[,₹\s]|rs\.?|inr/gi, '').replace(/^\((.*)\)$/, '$1')
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : null
}

function matches(item, target) {
  if (!item.str?.trim()) return false
  if (target.numeric) {
    const n = asNumber(item.str)
    return n != null && Math.abs(n - target.value) < 0.005
  }
  const a = clean(item.str)
  const b = clean(String(target.value))
  return b.length > 0 && (a.includes(b) || (a.length >= 4 && b.includes(a)))
}

async function findOnPage(pdf, pageNo, target) {
  const page = await pdf.getPage(pageNo)
  const text = await page.getTextContent()
  return { page, items: text.items, hit: text.items.find(it => matches(it, target)) || null }
}

export function PdfViewer({ url, page, onPage, target, filename }) {
  const wrap = useRef(null)
  const canvas = useRef(null)
  const [pdf, setPdf] = useState(null)
  const [error, setError] = useState('')
  const [width, setWidth] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [box, setBox] = useState(null)
  const [noText, setNoText] = useState(false)
  const [missed, setMissed] = useState(false)

  useEffect(() => {
    let live = true
    const task = pdfjs.getDocument(url)
    task.promise.then(d => live && setPdf(d)).catch(e => live && setError(e?.message || 'Could not open the PDF'))
    return () => { live = false; task.destroy() }
  }, [url])

  useEffect(() => {
    const el = wrap.current
    if (!el) return undefined
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // A target without a known page: look through the pages for it and open the first that has it.
  useEffect(() => {
    if (!pdf || !target || target.page) return
    let stop = false
    ;(async () => {
      for (let p = 1; p <= pdf.numPages && !stop; p += 1) {
        const { hit } = await findOnPage(pdf, p, target)
        if (hit) { if (!stop && p !== page) onPage(p); return }
      }
    })()
    return () => { stop = true }
  }, [pdf, target]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!pdf || !width || !canvas.current) return undefined
    let cancelled = false
    let render = null
    ;(async () => {
      const n = Math.min(Math.max(1, page), pdf.numPages)
      const { page: p, items, hit } = await findOnPage(pdf, n, target || { value: '' })
      if (cancelled) return
      const base = p.getViewport({ scale: 1 })
      const scale = ((width - 32) / base.width) * zoom
      const viewport = p.getViewport({ scale })
      const ratio = window.devicePixelRatio || 1
      const c = canvas.current
      c.width = Math.floor(viewport.width * ratio)
      c.height = Math.floor(viewport.height * ratio)
      c.style.width = `${Math.floor(viewport.width)}px`
      c.style.height = `${Math.floor(viewport.height)}px`
      render = p.render({ canvasContext: c.getContext('2d'), viewport, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null })
      await render.promise.catch(() => {})
      if (cancelled) return
      setNoText(items.filter(it => it.str?.trim()).length < 5)
      setMissed(!!target && !hit)
      if (target && hit) {
        const t = pdfjs.Util.transform(viewport.transform, hit.transform)
        const h = Math.hypot(t[2], t[3])
        const w = hit.width * scale
        setBox(target.row
          ? { left: 8, top: t[5] - h - 4, width: viewport.width - 16, height: h + 8 }
          : { left: t[4] - 4, top: t[5] - h - 3, width: w + 8, height: h + 6 })
        // bring the highlight into view
        const scroller = wrap.current
        if (scroller) scroller.scrollTo({ top: Math.max(0, t[5] - scroller.clientHeight / 2), behavior: 'smooth' })
      } else {
        setBox(null)
      }
    })()
    return () => { cancelled = true; render?.cancel() }
  }, [pdf, page, width, zoom, target])

  const pages = pdf?.numPages || 0
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-line px-3 py-2 text-sm">
        <button type="button" onClick={() => onPage(Math.max(1, page - 1))} disabled={page <= 1} className="rounded p-1 text-ink-2 hover:bg-subtle disabled:opacity-30" aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
        <span className="num min-w-[5.5rem] text-center text-ink-2">Page {page} of {pages || '–'}</span>
        <button type="button" onClick={() => onPage(Math.min(pages, page + 1))} disabled={page >= pages} className="rounded p-1 text-ink-2 hover:bg-subtle disabled:opacity-30" aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
        <span className="mx-2 h-4 w-px bg-line" />
        <button type="button" onClick={() => setZoom(z => Math.max(0.75, z - 0.25))} className="rounded p-1 text-ink-2 hover:bg-subtle" aria-label="Zoom out"><Minus className="h-4 w-4" /></button>
        <span className="num w-11 text-center text-xs text-ink-3">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom(z => Math.min(2.5, z + 0.25))} className="rounded p-1 text-ink-2 hover:bg-subtle" aria-label="Zoom in"><Plus className="h-4 w-4" /></button>
        <a href={url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs text-ink-3 hover:bg-subtle hover:text-ink">Open file<ExternalLink className="h-3 w-3" /></a>
      </div>
      {target && (noText || missed) && (
        <div className="flex items-center gap-2 border-b border-line bg-subtle px-4 py-1.5 text-xs text-ink-2">
          <ScanLine className="h-3.5 w-3.5 shrink-0 text-ink-3" />
          {noText ? 'This page is a scan, so the value can only be found by eye. It was read with OCR.' : 'The value is not printed as text on this page. Look for it by eye.'}
        </div>
      )}
      <div ref={wrap} className="scroll-thin relative flex-1 overflow-auto bg-subtle p-4">
        {error ? <p className="p-6 text-sm text-bad">{error}. <a href={url} className="underline">Open the file</a> instead.</p> : (
          <div className="relative mx-auto w-fit bg-white shadow-sheet">
            <canvas ref={canvas} aria-label={filename} role="img" />
            {box && <div key={`${box.top}-${box.left}`} className={`locate-box ${target?.tone === 'warn' ? 'is-doubt' : ''}`} style={box} />}
          </div>
        )}
      </div>
    </div>
  )
}

export function ImageViewer({ url, filename }) {
  const [zoom, setZoom] = useState(1)
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-line px-3 py-2 text-sm">
        <span className="text-ink-2">Photo</span>
        <span className="mx-2 h-4 w-px bg-line" />
        <button type="button" onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="rounded p-1 text-ink-2 hover:bg-subtle" aria-label="Zoom out"><Minus className="h-4 w-4" /></button>
        <span className="num w-11 text-center text-xs text-ink-3">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom(z => Math.min(3, z + 0.25))} className="rounded p-1 text-ink-2 hover:bg-subtle" aria-label="Zoom in"><Plus className="h-4 w-4" /></button>
        <a href={url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs text-ink-3 hover:bg-subtle hover:text-ink">Open file<ExternalLink className="h-3 w-3" /></a>
      </div>
      <div className="border-b border-line bg-subtle px-4 py-1.5 text-xs text-ink-2">A phone photo has no text layer, so values are found by eye. It was read with OCR.</div>
      <div className="scroll-thin flex-1 overflow-auto bg-subtle p-4">
        <img src={url} alt={filename} className="mx-auto max-w-none bg-white shadow-sheet" style={{ width: `${zoom * 100}%` }} />
      </div>
    </div>
  )
}
