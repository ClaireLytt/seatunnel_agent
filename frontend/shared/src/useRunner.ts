import { useState } from 'react'

/**
 * Wraps a page's async action with the busy/error/result state machine every
 * page repeats. `run` normalizes any thrown value to `message`; `setError`
 * lets pages reuse the error slot for local gates (e.g. empty-input notices,
 * whose i18n copy already carries the prefix); `reset` clears both.
 */
export function useRunner<A extends unknown[], T>(fn: (...args: A) => Promise<T>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<T | null>(null)

  const run = async (...args: A) => {
    setBusy(true)
    setError('')
    try {
      setResult(await fn(...args))
    } catch (e) {
      setResult(null)
      setError(`${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const reset = () => {
    setError('')
    setResult(null)
  }

  return { busy, error, result, run, reset, setError }
}
