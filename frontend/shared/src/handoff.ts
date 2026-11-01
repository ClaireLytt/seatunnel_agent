// Cross-page handoff over sessionStorage: one named key per receiving
// page. Every page that sends or receives a handoff goes through this
// module, so the key names and the receive protocol (take once, then
// run) live in exactly one place.
import { useEffect, useRef } from 'react'

export const HANDOFF = {
  backfill: 'seatunnel.handoff.backfill',
  backfillsql: 'seatunnel.handoff.backfillsql',
  dagopt: 'seatunnel.handoff.dagopt',
  indexadvisor: 'seatunnel.handoff.indexadvisor',
  qualitytrace: 'seatunnel.handoff.qualitytrace',
  sqlcost: 'seatunnel.handoff.sqlcost',
} as const

export type HandoffTarget = keyof typeof HANDOFF

/** Store the payload for the target page and navigate to it. */
export function sendHandoff(target: HandoffTarget, payload: string): void {
  sessionStorage.setItem(HANDOFF[target], payload)
  window.location.href = `/${target}/`
}

/** Read-and-clear the pending payload for this page, if any. */
export function takeHandoff(target: HandoffTarget): string | null {
  const payload = sessionStorage.getItem(HANDOFF[target])
  if (payload !== null) sessionStorage.removeItem(HANDOFF[target])
  return payload
}

/**
 * Run `receive` once on mount with the pending payload, if any. The
 * key is cleared before the callback, so a second mount is a no-op.
 * The latest `receive` is kept in a ref, so callers may pass a fresh
 * closure every render without re-triggering the effect.
 */
export function useHandoffReceive(target: HandoffTarget, receive: (payload: string) => void): void {
  const receiveRef = useRef(receive)
  receiveRef.current = receive
  useEffect(() => {
    const payload = takeHandoff(target)
    if (payload !== null) receiveRef.current(payload)
  }, [target])
}
