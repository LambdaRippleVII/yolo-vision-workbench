/** 定义与后端 WebSocket 协议对应的前端消息和状态类型。 */

export interface ErrorPayload {
  code: string
  message: string
  detail?: Record<string, unknown> | null
}

export interface Envelope<T = Record<string, unknown>> {
  type: string
  id?: string | null
  data: T
  ts: number
  error?: ErrorPayload | null
}

export interface HelloData {
  server_version: string
  protocol_version: number
  features: string[]
}

export interface HealthData {
  ok: boolean
  status: string
  version: string
  pid: number
  host?: string
  port?: number
}

export interface LogRecord {
  level: string
  message: string
  logger: string
  ts_text: string
  extra?: Record<string, unknown>
}
