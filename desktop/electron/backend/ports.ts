/**
 * Port helpers: find free port, probe existing backend.
 */
import { createServer } from 'net'

export async function isPortFree(port: number, host = '127.0.0.1'): Promise<boolean> {
  return new Promise((resolve) => {
    const srv = createServer()
    srv.once('error', () => resolve(false))
    srv.once('listening', () => {
      srv.close(() => resolve(true))
    })
    srv.listen(port, host)
  })
}

export async function findFreePort(startPort: number, host = '127.0.0.1', maxTries = 20): Promise<number> {
  for (let i = 0; i < maxTries; i++) {
    const port = startPort + i
    if (await isPortFree(port, host)) return port
  }
  throw new Error(`没有可用端口（已尝试 ${startPort}~${startPort + maxTries - 1}）`)
}

export interface HealthProbe {
  ok: boolean
  product?: string
  version?: string
  pid?: number
}

export async function probeBackendHealth(host: string, port: number, timeoutMs = 1500): Promise<HealthProbe> {
  try {
    const res = await fetch(`http://${host}:${port}/health`, {
      signal: AbortSignal.timeout(timeoutMs)
    })
    if (!res.ok) return { ok: false }
    const data = (await res.json()) as HealthProbe
    return { ok: true, product: data.product, version: data.version, pid: data.pid }
  } catch {
    return { ok: false }
  }
}

/** True if something listens but is not our backend (port conflict). */
export async function isForeignPortBusy(host: string, port: number): Promise<boolean> {
  const free = await isPortFree(port, host)
  if (free) return false
  const health = await probeBackendHealth(host, port)
  return !health.ok
}
