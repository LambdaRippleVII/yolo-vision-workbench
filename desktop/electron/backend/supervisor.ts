/**
 * ProcessSupervisor: spawn / health-check / restart / stop the Python backend.
 * Port strategy: reuse existing YOLO backend → else free port scan → else friendly error.
 */
import { spawn, ChildProcess, execFile } from 'child_process'
import { EventEmitter } from 'events'
import { existsSync } from 'fs'
import { join, resolve } from 'path'
import { platform } from 'os'
import { findFreePort, probeBackendHealth } from './ports'

export type BackendStatus =
  | 'stopped'
  | 'starting'
  | 'ready'
  | 'unhealthy'
  | 'restarting'
  | 'failed'
  | 'reused'

export interface SupervisorOptions {
  /** Absolute path to repo root (contains backend/). */
  rootDir: string
  host: string
  port: number
  /** Optional explicit python executable. */
  pythonPath?: string
  healthTimeoutMs?: number
  healthIntervalMs?: number
  maxRestarts?: number
  /** Dev: attach to an already-running backend instead of spawning. */
  attachMode?: boolean
  /** Try next ports when preferred is taken. */
  autoPort?: boolean
}

export interface SupervisorStatus {
  status: BackendStatus
  restarts: number
  port: number
  host: string
  message?: string
  reusedPid?: number
}

export class ProcessSupervisor extends EventEmitter {
  private opts: Required<Omit<SupervisorOptions, 'pythonPath' | 'attachMode'>> & {
    pythonPath?: string
    attachMode: boolean
    autoPort: boolean
  }
  private child: ChildProcess | null = null
  private status: BackendStatus = 'stopped'
  private restarts = 0
  private healthTimer: NodeJS.Timeout | null = null
  private stopping = false
  private reusedPid: number | undefined
  private message = ''

  constructor(options: SupervisorOptions) {
    super()
    this.opts = {
      rootDir: options.rootDir,
      host: options.host,
      port: options.port,
      healthTimeoutMs: options.healthTimeoutMs ?? 60_000,
      healthIntervalMs: options.healthIntervalMs ?? 5_000,
      maxRestarts: options.maxRestarts ?? 3,
      pythonPath: options.pythonPath,
      attachMode: options.attachMode ?? false,
      autoPort: options.autoPort ?? true
    }
  }

  getStatus(): SupervisorStatus {
    return {
      status: this.status,
      restarts: this.restarts,
      port: this.opts.port,
      host: this.opts.host,
      message: this.message || undefined,
      reusedPid: this.reusedPid
    }
  }

  private setStatus(status: BackendStatus, message?: string): void {
    this.status = status
    if (message !== undefined) this.message = message
    this.emit('status', this.getStatus())
  }

  /** Locate backend package dir (dev repo or packaged extraResources). */
  private resolveBackendDir(): string {
    const candidates = [
      join(this.opts.rootDir, 'backend'),
      join(this.opts.rootDir, 'resources', 'backend'),
      // packaged: <install>/resources/backend
      join(process.resourcesPath || '', 'backend'),
      join(this.opts.rootDir, '..', 'backend')
    ]
    for (const c of candidates) {
      if (c && existsSync(join(c, 'app', 'main.py'))) return resolve(c)
    }
    return join(this.opts.rootDir, 'backend')
  }

  /** Find a usable Python interpreter. */
  private resolvePython(): string {
    // 1) explicit
    if (this.opts.pythonPath && existsSync(this.opts.pythonPath)) {
      return this.opts.pythonPath
    }
    // 2) env override
    const envPy = process.env.YOLO_STUDIO_PYTHON
    if (envPy && existsSync(envPy)) return envPy

    // 3) bundled embeddable runtime (installer / portable)
    const bundled = [
      join(process.resourcesPath || '', 'python-embed', 'runtime', 'python.exe'),
      join(this.opts.rootDir, 'python-embed', 'runtime', 'python.exe'),
      join(this.opts.rootDir, 'resources', 'python-embed', 'runtime', 'python.exe')
    ]
    for (const p of bundled) {
      if (p && existsSync(p)) return p
    }

    // 4) project venv
    const backendDir = this.resolveBackendDir()
    const venvCandidates =
      platform() === 'win32'
        ? [
            join(backendDir, '.venv', 'Scripts', 'python.exe'),
            join(this.opts.rootDir, 'backend', '.venv', 'Scripts', 'python.exe')
          ]
        : [join(backendDir, '.venv', 'bin', 'python'), join(this.opts.rootDir, 'backend', '.venv', 'bin', 'python')]
    for (const p of venvCandidates) {
      if (existsSync(p)) return p
    }

    // 5) system interpreters
    if (platform() === 'win32') {
      return 'py'
    }
    return 'python3'
  }

  /** Extra args for `py` launcher (needs -3). */
  /**
   * Launch via backend/run_backend.py so embeddable Python (._pth) finds `app`.
   */
  private pythonArgs(backendDir: string): string[] {
    const py = this.resolvePython()
    const script = join(backendDir, 'run_backend.py')
    const base = [script]
    if (platform() === 'win32' && /(^|[\\/])py(\.exe)?$/i.test(py)) {
      return ['-3', ...base]
    }
    return base
  }

  private get wsUrl(): string {
    return `ws://${this.opts.host}:${this.opts.port}/ws`
  }

  getWsUrl(): string {
    return this.wsUrl
  }

  /** Prefer: existing backend → free port on preferred → next free port. */
  private async resolvePort(): Promise<{ port: number; reuse: boolean; pid?: number; note: string }> {
    const host = this.opts.host
    const preferred = this.opts.port

    const existing = await probeBackendHealth(host, preferred)
    if (existing.ok) {
      return {
        port: preferred,
        reuse: true,
        pid: existing.pid,
        note: `检测到已有后端服务，直接复用（端口 ${preferred}，PID ${existing.pid ?? '?'}）`
      }
    }

    // Preferred free?
    try {
      const free = await findFreePort(preferred, host, 1)
      return { port: free, reuse: false, note: `使用端口 ${free}` }
    } catch {
      /* fall through */
    }

    if (!this.opts.autoPort) {
      throw new Error(
        `端口 ${preferred} 已被其他程序占用。请关闭占用程序，或在设置中更换端口。`
      )
    }

    const next = await findFreePort(preferred + 1, host, 30)
    return {
      port: next,
      reuse: false,
      note: `端口 ${preferred} 被占用，已自动改用 ${next}`
    }
  }

  async start(): Promise<void> {
    this.stopping = false
    this.reusedPid = undefined

    let resolved
    try {
      resolved = await this.resolvePort()
    } catch (err) {
      this.setStatus('failed', String(err))
      this.emit('log', { level: 'ERROR', source: 'supervisor', message: String(err) })
      throw err
    }

    this.opts.port = resolved.port
    this.emit('log', { level: 'INFO', source: 'supervisor', message: resolved.note })

    if (resolved.reuse) {
      this.reusedPid = resolved.pid
      this.setStatus('reused', resolved.note)
      // still mark ready
      await this.waitHealthy()
      return
    }

    if (this.opts.attachMode) {
      await this.waitHealthy()
      return
    }

    await this.spawnBackend()
    await this.waitHealthy()
  }

  /** Free port if occupied by non-healthy process is left to user; we only auto-shift. */

  private async spawnBackend(): Promise<void> {
    if (this.child) return
    this.setStatus('starting', '正在启动后端服务…')

    const backendDir = this.resolveBackendDir()
    const python = this.resolvePython()
    const args = this.pythonArgs(backendDir)

    const env = {
      ...process.env,
      YOLO_STUDIO_ROOT: this.opts.rootDir,
      YOLO_STUDIO_HOST: this.opts.host,
      YOLO_STUDIO_PORT: String(this.opts.port),
      PYTHONUTF8: '1',
      PYTHONPATH: backendDir
    }

    this.emit('log', {
      level: 'INFO',
      source: 'supervisor',
      message: `启动后端 python=${python} cwd=${backendDir} port=${this.opts.port}`
    })
    this.child = spawn(python, args, {
      cwd: backendDir,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    })
    this.child.on('error', (err) => {
      const msg =
        (err as NodeJS.ErrnoException).code === 'ENOENT'
          ? '未找到 Python。请安装 Python 3.11+，或设置环境变量 YOLO_STUDIO_PYTHON 指向 python.exe'
          : `后端启动失败: ${err.message}`
      this.emit('log', {
        level: 'ERROR',
        source: 'supervisor',
        message: msg
      })
      this.setStatus('failed', msg)
    })
    const logLine = (buf: Buffer) => {
      const line = buf.toString().trimEnd()
      if (!line) return
      const level = /ERROR|CRITICAL|Traceback/i.test(line)
        ? 'ERROR'
        : /WARN|WARNING/i.test(line)
          ? 'WARN'
          : 'INFO'
      this.emit('log', { level, source: 'backend', message: line })
    }
    this.child.stdout?.on('data', logLine)
    this.child.stderr?.on('data', logLine)

    this.child.on('exit', (code, signal) => {
      this.child = null
      this.clearHealthTimer()
      if (this.stopping) {
        this.setStatus('stopped', '后端已停止')
        return
      }
      this.emit('log', {
        level: 'ERROR',
        source: 'supervisor',
        message: `后端进程退出 code=${code} signal=${signal}`
      })
      this.tryRestart()
    })
  }

  private tryRestart(): void {
    if (this.stopping) return
    if (this.restarts >= this.opts.maxRestarts) {
      this.setStatus('failed', '后端多次启动失败，请查看日志')
      return
    }
    this.restarts += 1
    this.setStatus('restarting', `正在重启后端（第 ${this.restarts} 次）…`)
    const delay = Math.min(1000 * 2 ** (this.restarts - 1), 10_000)
    this.emit('log', {
      level: 'WARN',
      source: 'supervisor',
      message: `重启后端 attempt=${this.restarts} delay=${delay}ms`
    })
    setTimeout(() => {
      if (!this.stopping) {
        void this.spawnBackend().then(() => this.waitHealthy())
      }
    }, delay)
  }

  private async fetchHealth(): Promise<boolean> {
    const probe = await probeBackendHealth(this.opts.host, this.opts.port, 2000)
    return probe.ok
  }

  private async waitHealthy(): Promise<void> {
    const deadline = Date.now() + this.opts.healthTimeoutMs
    while (Date.now() < deadline) {
      if (this.stopping) return
      if (await this.fetchHealth()) {
        this.setStatus('ready', this.message || `后端就绪 · ${this.opts.host}:${this.opts.port}`)
        this.startHealthTimer()
        return
      }
      await new Promise((r) => setTimeout(r, 500))
    }
    this.setStatus('failed', '后端启动超时，请检查日志')
    this.emit('log', {
      level: 'ERROR',
      source: 'supervisor',
      message: '后端健康检查超时'
    })
  }

  private startHealthTimer(): void {
    this.clearHealthTimer()
    this.healthTimer = setInterval(() => {
      void this.fetchHealth().then((ok) => {
        if (this.stopping) return
        if (!ok) {
          this.setStatus('unhealthy', '后端状态异常')
          this.emit('log', {
            level: 'WARN',
            source: 'supervisor',
            message: '后端健康检查失败'
          })
        } else if (this.status !== 'ready' && this.status !== 'reused') {
          this.setStatus('ready', `后端就绪 · ${this.opts.host}:${this.opts.port}`)
        }
      })
    }, this.opts.healthIntervalMs)
  }

  private clearHealthTimer(): void {
    if (this.healthTimer) {
      clearInterval(this.healthTimer)
      this.healthTimer = null
    }
  }

  async stop(): Promise<void> {
    this.stopping = true
    this.clearHealthTimer()

    const child = this.child
    if (!child) {
      this.setStatus('stopped', '后端已停止')
      return
    }

    await new Promise<void>((resolveStop) => {
      const done = () => resolveStop()
      child.once('exit', done)

      if (platform() === 'win32') {
        execFile('taskkill', ['/pid', String(child.pid), '/T', '/F'], () => {
          /* exit handler will resolve */
        })
      } else {
        child.kill('SIGTERM')
        setTimeout(() => {
          if (!child.killed) child.kill('SIGKILL')
        }, 3000)
      }

      setTimeout(done, 5000)
    })

    this.child = null
    this.setStatus('stopped', '后端已停止')
  }
}
