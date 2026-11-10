import { useCallback, useEffect, useRef, useState } from 'react'

// Load `fetcher()` now, then every `ms` while `keepPolling(data)` is true — used to follow an
// application through the queue. Polling pauses while the tab is hidden.
export default function usePolling(fetcher, keepPolling, ms = 2500) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const reload = useCallback(async () => {
    try {
      setData(await fetcherRef.current())
      setError(null)
    } catch (err) {
      setError(err)
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  const polling = data != null && keepPolling(data)
  useEffect(() => {
    if (!polling) return undefined
    const id = setInterval(() => { if (!document.hidden) reload() }, ms)
    return () => clearInterval(id)
  }, [polling, reload, ms])

  return { data, error, reload, setData }
}
