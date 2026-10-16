/** 管理与本地后端的 WebSocket 连接、请求应答、心跳和断线重连。 */

import type { Envelope, LogRecord } from './protocol'

type MessageHandler = (msg: Envelope) => void

/** 为渲染进程提供带超时和自动重连能力的 WebSocket 客户端。 */
export class WsClient {
  private ws: WebSocket | null = null
  private url = ''
  private reqSeq = 0
  private pending = new Map<string, { resolve: (v: Envelope) => void; reject: (e: Error) => void }>()
  private handlers = new Map<string, Set<MessageHandler>>()
  private pingTimer: number | null = null
  private reconnectDelay = 1000
  private closedByUser = false
  private socketGeneration = 0

  connect(url: string): void {
    this.url = url
    this.closedByUser = false
    const generation = ++this.socketGeneration
    const previous = this.ws
    this.ws = null
    this.stopPing()
    if (previous) {
      this.rejectPending('WebSocket endpoint changed')
      previous.close()
    }
    this.open(generation)
  }

  private open(generation = this.socketGeneration): void {
    if (generation !== this.socketGeneration || this.closedByUser) return
    if (this.ws) {
      const previous = this.ws
      this.ws = null
      previous.close()
    }
    const ws = new WebSocket(this.url)
    this.ws = ws

    ws.onopen = () => {
      if (generation !== this.socketGeneration) {
        ws.close()
        return
      }
      this.reconnectDelay = 1000
      this.emitLocal('client.open', { url: this.url })
      this.startPing()
    }

    // 忽略旧连接迟到的事件，避免它覆盖新连接状态。
    ws.onmessage = (ev) => {
      if (generation !== this.socketGeneration) return
      let msg: Envelope
      try {
        msg = JSON.parse(String(ev.data)) as Envelope
      } catch {
        return
      }
      // 先按请求编号完成对应请求的响应。
      if (msg.id && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id)!
        this.pending.delete(msg.id)
        if (msg.error) {
          p.reject(new Error(`${msg.error.code}: ${msg.error.message}`))
        } else {
          p.resolve(msg)
        }
      }
      // 再按消息类型分发给页面订阅者。
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
      if (generation !== this.socketGeneration) return
      this.ws = null
      this.stopPing()
      this.rejectPending('WebSocket disconnected')
      this.emitLocal('client.close', {})
      if (!this.closedByUser) {
        window.setTimeout(() => this.open(generation), this.reconnectDelay)
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15_000)
      }
    }

    ws.onerror = () => {
      // 浏览器随后会触发 onclose 并统一处理断线。
    }
  }

  private startPing(): void {
    this.stopPing()
    this.pingTimer = window.setInterval(() => {
      void this.request('ping', {}).catch(() => {
        /* 心跳丢失由 onclose 的重连流程统一处理。 */
      })
    }, 15_000)
  }

  private stopPing(): void {
    if (this.pingTimer !== null) {
      window.clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private rejectPending(message: string): void {
    for (const request of this.pending.values()) request.reject(new Error(message))
    this.pending.clear()
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

  /** 发送带唯一请求编号的消息，并等待匹配响应或超时。 */
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
    this.socketGeneration += 1
    this.stopPing()
    this.rejectPending('WebSocket closed')
    const current = this.ws
    this.ws = null
    current?.close()
  }
}

// 前端各页面共用的长连接实例。
export const wsClient = new WsClient()

export async function fetchHealth(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(2000) })
    return res.ok
  } catch {
    return false
  }
}
