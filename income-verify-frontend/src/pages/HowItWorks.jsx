import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'

// The two animated diagrams (diagram only; the text around them is written here), rendered by the arch_diagram skill (docs/diagrams → public/diagrams).
// Each is a self-contained HTML page shown in an iframe; it follows the app's light/dark theme.
const DIAGRAMS = [
  {
    file: 'flow', ratio: 2260 / 780, title: 'How a file is checked',
    problem: 'An underwriter spends hours per file matching payslips, bank statements and Form 16 by hand, and edited PDFs still slip through.',
    how: 'An AI model only reads the documents. Every sum, match and decision after that is plain Python, and every flag points to the page it came from.',
    legend: [['AI model reads', 'brand'], ['Python checks and decides', 'ink'], ['A person, only when needed', 'warn']],
  },
  {
    file: 'architecture', ratio: 1940 / 660, title: 'How it is built',
    problem: 'Files take up to two minutes to read, model APIs sometimes fail, and a reviewer is watching the page while it happens.',
    how: 'The API never runs a model. It stores the upload and queues a small task; Python workers do the slow work, retry it, and write results and progress to Postgres, which the page polls.',
    legend: [['Our services', 'brand'], ['Data and queue', 'ink'], ['External APIs', 'warn']],
  },
]

const CHIP = { brand: 'border-brand-600/30 bg-brand-600/10 text-brand-600', ink: 'border-ink-3/30 bg-ink/5 text-ink-2', warn: 'border-warn/30 bg-warn/10 text-warn' }
const DOT = { brand: 'bg-brand-600', ink: 'bg-ink-2', warn: 'bg-warn' }

function useDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const obs = new MutationObserver(() => setDark(document.documentElement.classList.contains('dark')))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}

function Diagram({ d, dark }) {
  return (
    <section className="space-y-4">
      <h2 className="font-serif text-[1.9rem] leading-tight text-ink">{d.title}</h2>
      <div className="max-w-3xl space-y-2 text-[15px] leading-relaxed text-ink-2">
        <p className="border-l-2 border-warn pl-4"><span className="font-semibold text-warn">The problem. </span>{d.problem}</p>
        <p className="border-l-2 border-ok pl-4"><span className="font-semibold text-ok">How it works. </span>{d.how}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {d.legend.map(([label, tone]) => (
          <span key={label} className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${CHIP[tone]}`}><span className={`h-1.5 w-1.5 rounded-full ${DOT[tone]}`} />{label}</span>
        ))}
        <span className="ml-auto flex gap-3 text-xs">
          <a href={`/diagrams/${d.file}.png`} download className="inline-flex items-center gap-1 text-ink-3 hover:text-ink"><Download className="h-3.5 w-3.5" />PNG</a>
          <a href={`/diagrams/${d.file}.mp4`} download className="inline-flex items-center gap-1 text-ink-3 hover:text-ink"><Download className="h-3.5 w-3.5" />Video</a>
        </span>
      </div>
      {/* full screen width (the diagrams are wide); below ~1400 px they scroll sideways instead of shrinking */}
      <div className="scroll-thin relative left-1/2 w-[calc(100vw-16px)] max-w-[1880px] -translate-x-1/2 overflow-x-auto px-4 sm:px-6">
        <iframe
          key={dark ? 'dark' : 'light'}
          title={d.title}
          src={`/diagrams/${d.file}.html?theme=${dark ? 'dark' : 'light'}`}
          className="mx-auto block w-full min-w-[1360px] rounded-[18px] border-0 bg-transparent"
          style={{ aspectRatio: d.ratio }}
          loading="lazy"
        />
      </div>
    </section>
  )
}

export default function HowItWorks() {
  const dark = useDark()
  return (
    <div className="space-y-16">
      <header className="max-w-3xl">
        <h1 className="font-serif text-[2.6rem] leading-[1.1] tracking-tight text-ink">How it works</h1>
        <p className="mt-3 text-[17px] leading-relaxed text-ink-2">The path a loan file takes from upload to verdict, and the system underneath it. The moving dashes show the direction work flows.</p>
      </header>
      {DIAGRAMS.map(d => <Diagram key={d.file} d={d} dark={dark} />)}
    </div>
  )
}
