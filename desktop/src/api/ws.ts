/** Minimal WebSocket client: connect, heartbeat, request/response, events. */

import type { Envelope, LogRecord } from './protocol'

type MessageHandler = (msg: Envelope) => void

export class WsClient {
  private ws: WebSocket | null = null
  private url = ''
  private reqSeq = 0
  private pending = new Map<string, { resolve: (v: Envelope) => void; reject: (e: Error) => void }>()
  private handlers = new Map<string, Set<MessageHandler>>()
  private pingTimer: number | null = null
  private reconnectDelay = 1000
  private closedByUser = false

  connect(url: string): void {
    this.url = url
    this.closedByUser = false
    this.open()
  }

  private open(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    const ws = new WebSocket(this.url)
    this.ws = ws

    ws.onopen = () => {
      this.reconnectDelay = 1000
      this.emitLocal('client.open', { url: this.url })
      this.startPing()
    }

    ws.onmessage = (ev) => {
      let msg: Envelope
      try {
        msg = JSON.parse(String(ev.data)) as Envelope
      } catch {
        return
      }
      // Resolve request/response
      if (msg.id && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id)!
        this.pending.delete(msg.id)
        if (msg.error) {
          p.reject(new Error(`${msg.error.code}: ${msg.error.message}`))
        } else {
          p.resolve(msg)
        }
      }
      // Dispatch by type
      const set = this.handlers.get(msg.type)
      if (set) {
        for (const h of set) h(msg)
      }
      const anySet = this.handlers.get('*')
      if (anySet) {
        for (const h of anySet) h(msg)
      }
    }

    ws.onclose = () => {
      this.stopPing()
      this.emitLocal('client.close', {})
      if (!this.closedByUser) {
        window.setTimeout(() => this.open(), this.reconnectDelay)
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15_000)
      }
    }

    ws.onerror = () => {
      // onclose will follow
    }
  }

  private startPing(): void {
    this.stopPing()
    this.pingTimer = window.setInterval(() => {
      void this.request('ping', {}).catch(() => {
        /* heartbeat miss handled by onclose */
      })
    }, 15_000)
  }

  private stopPing(): void {
    if (this.pingTimer !== null) {
      window.clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private emitLocal(type: string, data: Record<string, unknown>): void {
    const set = this.handlers.get(type)
    if (set) {
      const msg: Envelope = { type, data, ts: Date.now() }
      for (const h of set) h(msg)
    }
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) this.handlers.set(type, new Set())
    this.handlers.get(type)!.add(handler)
    return () => this.handlers.get(type)?.delete(handler)
  }

  request<T = Record<string, unknown>>(type: string, data: Record<string, unknown>, timeoutMs = 30_000): Promise<Envelope<T>> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket not connected'))
        return
      }
      const id = `r${++this.reqSeq}`
      const envelope: Envelope = { type, id, data, ts: Date.now() }
      const timer = window.setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`request timeout: ${type}`))
      }, timeoutMs)
      this.pending.set(id, {
        resolve: (v) => {
          window.clearTimeout(timer)
          resolve(v as Envelope<T>)
        },
        reject: (e) => {
          window.clearTimeout(timer)
          reject(e)
        }
      })
      this.ws.send(JSON.stringify(envelope))
    })
  }

  close(): void {
    this.closedByUser = true
    this.stopPing()
    this.ws?.close()
    this.ws = null
  }
}

export const wsClient = new WsClient()

export async function fetchHealth(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(2000) })
    return res.ok
  } catch {
    return false
  }
}
