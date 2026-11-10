import { Suspense, lazy, useEffect } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { HelpCircle, Moon, Plus, Sun } from 'lucide-react'
import Applications from '@/pages/Applications'
import NewApplication from '@/pages/NewApplication'
import ApplicationDetail from '@/pages/ApplicationDetail'
import Stats from '@/pages/Stats'
import HowItWorks from '@/pages/HowItWorks'
import { EmptyState, PageLoader, buttonClass } from '@/components/ui'
import useTheme from '@/lib/theme'

// The review page carries pdf.js, so it loads only when opened.
const DocumentReview = lazy(() => import('@/pages/DocumentReview'))

/** The mark: a ring with a tick, like a verification seal. */
export function Seal({ className = 'h-7 w-7' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="7" className="fill-ink" />
      <circle cx="16" cy="16" r="9.5" fill="none" strokeWidth="1.6" className="stroke-brand-500" />
      <path d="M11.5 16.4l3.1 3.1 6-6.3" fill="none" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="stroke-canvas" />
    </svg>
  )
}

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500" aria-label="IncomeVerify home">
      <Seal />
      <span className="hidden font-serif text-[21px] font-medium tracking-tight text-ink sm:inline">IncomeVerify</span>
    </Link>
  )
}

function NotFound() {
  return (
    <EmptyState icon={HelpCircle} title="Page not found" action={<Link to="/" className={buttonClass()}>Back to applications</Link>}>
      The page you are looking for does not exist, or the application was deleted.
    </EmptyState>
  )
}

const navClass = ({ isActive }) => `relative shrink-0 px-1 py-5 text-sm font-medium transition-colors ${isActive ? 'text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-ink' : 'text-ink-3 hover:text-ink'}`

export default function App() {
  const { pathname } = useLocation()
  const { dark, toggle } = useTheme()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 border-b border-line bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-5 px-4 sm:gap-8 sm:px-6">
          <Logo />
          <nav className="scroll-thin flex min-w-0 items-center gap-5 overflow-x-auto whitespace-nowrap">
            <NavLink to="/" end className={navClass}>Applications</NavLink>
            <NavLink to="/how-it-works" className={navClass}>How it works</NavLink>
            <NavLink to="/stats" className={navClass}>Accuracy</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-1.5 sm:gap-3">
            <button type="button" onClick={toggle} className="rounded-md p-2 text-ink-3 hover:bg-subtle hover:text-ink" aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
              {dark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
            </button>
            <Link to="/new" className={buttonClass('primary', 'md')}><Plus className="h-4 w-4" /><span className="hidden sm:inline">New application</span></Link>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-7 sm:px-6 sm:py-10">
        <Routes>
          <Route path="/" element={<Applications />} />
          <Route path="/new" element={<NewApplication />} />
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="/documents/:id" element={<Suspense fallback={<PageLoader />}><DocumentReview /></Suspense>} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-x-6 gap-y-1 px-4 py-5 text-xs text-ink-3 sm:px-6">
          <span>Demo on synthetic documents. Uploads are deleted after 24 hours.</span>
          <span>The model reads the documents. Every sum, match and decision is plain Python.</span>
        </div>
      </footer>
    </div>
  )
}
