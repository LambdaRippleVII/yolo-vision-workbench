/** 协调 Python 后端的启动、端口探测、健康检查、复用和退出。 */
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
  /** 仓库根目录绝对路径，目录中包含 backend。 */
  rootDir: string
  /** 期望的后端版本；版本不匹配的既有服务不会被复用。 */
  version?: string
  host: string
  port: number
  /** 可选的显式 Python 可执行文件路径。 */
  pythonPath?: string
  healthTimeoutMs?: number
  healthIntervalMs?: number
  maxRestarts?: number
  /** 开发模式下连接已有后端，而不是再创建一个进程。 */
  attachMode?: boolean
  /** 首选端口被占用时是否继续尝试后续端口。 */
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

/** 管理后端进程生命周期，并通过事件向主进程报告状态和日志。 */
export class ProcessSupervisor extends EventEmitter {
  private opts: Required<Omit<SupervisorOptions, 'pythonPath' | 'attachMode' | 'version'>> & {
    pythonPath?: string
    attachMode: boolean
    autoPort: boolean
    version?: string
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
      version: options.version,
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

  setPythonPath(pythonPath?: string): void {
    this.opts.pythonPath = pythonPath
  }

  private setStatus(status: BackendStatus, message?: string): void {
    this.status = status
    if (message !== undefined) this.message = message
    this.emit('status', this.getStatus())
  }

  /** 在开发目录和安装包资源目录中定位后端代码。 */
  private resolveBackendDir(): string {
    const candidates = [
      join(this.opts.rootDir, 'backend'),
      join(this.opts.rootDir, 'resources', 'backend'),
      // 安装包运行时的资源目录。
      join(process.resourcesPath || '', 'backend'),
      join(this.opts.rootDir, '..', 'backend')
    ]
    for (const c of candidates) {
      if (c && existsSync(join(c, 'app', 'main.py'))) return resolve(c)
    }
    return join(this.opts.rootDir, 'backend')
  }

  /** 按显式配置、随包运行时、项目虚拟环境和系统解释器的优先级选择 Python。 */
  private resolvePython(): string {
    // 1) 显式指定的解释器。
    if (this.opts.pythonPath && existsSync(this.opts.pythonPath)) {
      return this.opts.pythonPath
    }
    // 2) 环境变量覆盖项。
    const envPy = process.env.YOLO_STUDIO_PYTHON
    if (envPy && existsSync(envPy)) return envPy

    // 3) 安装包或便携版随附的嵌入式运行时。
    const bundled = [
      join(process.resourcesPath || '', 'python-embed', 'runtime', 'python.exe'),
      join(this.opts.rootDir, 'python-embed', 'runtime', 'python.exe'),
      join(this.opts.rootDir, 'resources', 'python-embed', 'runtime', 'python.exe')
    ]
    for (const p of bundled) {
      if (p && existsSync(p)) return p
    }

    // 4) 项目虚拟环境。
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

    // 5) 系统级 Python 解释器。
    if (platform() === 'win32') {
      return 'py'
    }
    return 'python3'
  }

  /** 生成后端启动参数，并兼容 Windows 的 py 启动器和嵌入式 Python。 */
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

  /** 优先复用兼容服务，其次尝试首选端口，最后按需查找空闲端口。 */
  private async resolvePort(): Promise<{ port: number; reuse: boolean; pid?: number; note: string }> {
    const host = this.opts.host
    const preferred = this.opts.port

    const existing = await probeBackendHealth(host, preferred)
    if (existing.ok) {
      const compatible =
        existing.product === 'YOLO Vision Workbench' &&
        (!this.opts.version || existing.version === this.opts.version)
      if (compatible) {
        return {
          port: preferred,
          reuse: true,
          pid: existing.pid,
          note: `检测到同版本后端服务，直接复用（端口 ${preferred}，PID ${existing.pid ?? '?'}）`
        }
      }
      if (this.opts.attachMode) {
        const found = `${existing.product || '未知服务'}${existing.version ? ` ${existing.version}` : ''}`
        const expected = this.opts.version ? `，需要版本 ${this.opts.version}` : ''
        throw new Error(`端口 ${preferred} 上的服务不兼容（${found}${expected}），无法连接。`)
      }
    }

    // 先保留用户配置的端口；只有占用时才执行后续候选端口扫描。
    try {
      const free = await findFreePort(preferred, host, 1)
      return { port: free, reuse: false, note: `使用端口 ${free}` }
    } catch {
      /* 首选端口不可用时继续扫描其他端口。 */
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

    // 命中兼容的既有服务时只等待健康状态，不再启动第二个 Python 进程。
    if (resolved.reuse) {
      this.reusedPid = resolved.pid
      this.setStatus('reused', resolved.note)
      // 复用服务仍需等待健康检查通过。
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

  /** 非健康进程占用端口时保留现场，并由自动端口策略改用其他端口。 */

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
    /* 进程退出事件会完成停止 Promise。 */
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
