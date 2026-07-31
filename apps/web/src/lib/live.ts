/** Browser side of the live layer. Connects only to our own /api/live/ws —
 * the upstream (and its credentials) never leaves the server. Reconnects
 * with the same capped backoff ladder the server uses upstream. */

export const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000, 30000] as const

export function backoffMs(attempt: number): number {
  return BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]
}

export interface TickMsg {
  type: 'tick'
  instrument_token: number
  last_price: string
  change_pct: string | null
  received_at: string
}

export interface StateMsg {
  type: 'state'
  status: string
  reconnects: number
  last_tick_at?: string | null
  detail?: string
}

export interface SnapshotMsg {
  type: 'snapshot'
  state: StateMsg
  detail: string
  ticks: TickMsg[]
}

export type LiveMsg = TickMsg | StateMsg | SnapshotMsg | { type: 'heartbeat' }

export interface LiveSocket {
  close: () => void
}

/** Auto-reconnecting socket. `onStatus` reports the BROWSER's link to the
 * API ('open' | 'reconnecting'), independent of the server's upstream state
 * that arrives in state frames — two different truths, both shown. */
export function connectLive(
  onMessage: (msg: LiveMsg) => void,
  onStatus: (status: 'open' | 'reconnecting') => void,
): LiveSocket {
  let ws: WebSocket | null = null
  let attempt = 0
  let closed = false
  let timer: ReturnType<typeof setTimeout> | null = null

  const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/live/ws`

  function open() {
    if (closed) return
    ws = new WebSocket(url)
    ws.onopen = () => {
      attempt = 0
      onStatus('open')
    }
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data) as LiveMsg)
      } catch {
        /* a malformed frame is dropped, not fatal */
      }
    }
    ws.onclose = () => {
      if (closed) return
      onStatus('reconnecting')
      timer = setTimeout(open, backoffMs(attempt))
      attempt += 1
    }
    ws.onerror = () => ws?.close()
  }

  open()
  return {
    close: () => {
      closed = true
      if (timer) clearTimeout(timer)
      ws?.close()
    },
  }
}
