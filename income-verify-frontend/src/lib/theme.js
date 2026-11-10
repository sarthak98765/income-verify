import { useState } from 'react'

// Light / dark, remembered per browser. index.html applies it before first paint.
export default function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const toggle = () => {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    try { localStorage.setItem('theme', next ? 'dark' : 'light') } catch { /* private mode: not remembered */ }
    setDark(next)
  }
  return { dark, toggle }
}
