import { spawn, spawnSync, type ChildProcess } from 'child_process'
import { EventEmitter } from 'events'
import { promises as fs, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'fs'
import { join } from 'path'
import { StringDecoder } from 'string_decoder'

const RUNTIME_SCHEMA_VERSION = 1
const PIP_BOOTSTRAP_URL = 'https://bootstrap.pypa.io/get-pip.py'
const PYTORCH_CPU_INDEX = 'https://download.pytorch.org/whl/cpu'
const PYPI_INDEX = 'https://pypi.org/simple'

export type RuntimeSetupPhase = 'initializing' | 'ready' | 'failed'

export interface RuntimeSetupStatus {
  managed: boolean
  phase: RuntimeSetupPhase
  step: string
  message: string
  error: string
  details: string[]
}

export interface RuntimeSetupOptions {
  managed: boolean
  bundledRuntimeDir: string
  userDataDir: string
  backendDir: string
}

export class RuntimeSetup extends EventEmitter {
  private readonly options: RuntimeSetupOptions
  private readonly installDir: string
  private readonly pythonPath: string
  private readonly readyMarkerPath: string
  private details: string[] = []
  private process: ChildProcess | null = null
  private pending: Promise<string> | null = null
  private status: RuntimeSetupStatus

  constructor(options: RuntimeSetupOptions) {
    super()
    this.options = options
    this.installDir = join(options.userDataDir, 'python-runtime')
    this.pythonPath = join(this.installDir, 'python.exe')
    this.readyMarkerPath = join(this.installDir, 'runtime-ready.json')
    this.status = {
      managed: options.managed,
      phase: options.managed ? 'initializing' : 'ready',
      step: options.managed ? '准备运行环境' : '开发环境',
      message: options.managed ? '正在检查随包 Python 运行环境…' : '开发环境由当前 Python 配置提供。',
      error: '',
      details: []
    }
  }

  getStatus(): RuntimeSetupStatus {
    return { ...this.status, details: [...this.status.details] }
  }

  initialize(): Promise<string> {
    if (!this.options.managed) return Promise.resolve('')
    if (this.pending) return this.pending

    this.pending = this.initializeInternal().finally(() => {
      this.pending = null
    })
    return this.pending
  }

  async markReady(message = '推理环境和本地服务已就绪。'): Promise<void> {
    if (this.options.managed) await this.persistReadyMarker()
    this.update({ phase: 'ready', step: '完成', message, error: '' })
  }

  async markFailed(error: unknown): Promise<void> {
    const message = error instanceof Error ? error.message : String(error)
    this.addDetail(message)
    this.update({
      phase: 'failed',
      step: '初始化未完成',
      message: '运行环境或本地服务没有准备好。请检查网络、端口和文件权限后重试；详细信息见下方日志。',
      error: message
    })
  }

  terminate(): void {
    this.process?.kill()
  }

  private async initializeInternal(): Promise<string> {
    this.details = []
    this.update({
      phase: 'initializing',
      step: '1/5 · 准备 Python',
      message: '正在把随包 Python 复制到当前用户可写目录…',
      error: '',
      details: []
    })

    await this.copyRuntimeToUserData()
    this.enableEmbeddedSitePackages()

    if (this.hasReadyMarker()) {
      this.update({
        phase: 'initializing',
        step: '5/5 · 启动本地服务',
        message: '已找到准备完成的推理环境，正在启动本地服务…'
      })
      return this.pythonPath
    }

    await this.ensurePip()

    this.update({
      phase: 'initializing',
      step: '2/5 · 安装基础依赖',
      message: '正在安装后端和视频处理组件；首次安装需要联网下载。'
    })
    await this.runPipInstall(['-r', join(this.options.backendDir, 'requirements', 'base.txt')])

    this.update({
      phase: 'initializing',
      step: '3/5 · 安装 CPU 推理环境',
      message: '正在准备 CPU 版 PyTorch；安装时间取决于网络速度。'
    })
    await this.ensureCpuTorch()

    this.update({
      phase: 'initializing',
      step: '4/5 · 安装 YOLO 组件',
      message: '正在安装 Ultralytics 和 YOLO 推理依赖…'
    })
    await this.runPipInstall(['-r', join(this.options.backendDir, 'requirements', 'yolo.txt')])

    this.update({
      phase: 'initializing',
      step: '4/5 · 验证安装',
      message: '正在验证 Python、PyTorch 和 Ultralytics…'
    })
    await this.runInstallerProcess(
      this.pythonPath,
      [
        '-c',
        'import cv2, fastapi, torch, torchvision, ultralytics, uvicorn; assert torch.version.cuda is None, f"Expected CPU-only PyTorch, found CUDA {torch.version.cuda}"; print(f"环境验证通过：torch={torch.__version__} · ultralytics={ultralytics.__version__} · opencv={cv2.__version__}")'
      ],
      '4/5 · 验证安装',
      '正在验证本地推理组件…'
    )

    await this.persistReadyMarker()
    this.update({
      phase: 'initializing',
      step: '5/5 · 启动本地服务',
      message: '运行环境已安装，正在启动本地服务…'
    })
    return this.pythonPath
  }

  private async persistReadyMarker(): Promise<void> {
    await fs.writeFile(
      this.readyMarkerPath,
      JSON.stringify({
        schemaVersion: RUNTIME_SCHEMA_VERSION,
        torchMode: 'cpu',
        completedAt: new Date().toISOString()
      }),
      'utf8'
    )
  }

  private async copyRuntimeToUserData(): Promise<void> {
    if (existsSync(this.pythonPath)) return

    const sourcePython = join(this.options.bundledRuntimeDir, 'python.exe')
    if (!existsSync(sourcePython)) {
      throw new Error(`安装包中没有找到随包 Python：${sourcePython}`)
    }

    await fs.mkdir(this.options.userDataDir, { recursive: true })
    const stagedDir = join(this.options.userDataDir, 'python-runtime.installing')
    await fs.rm(stagedDir, { recursive: true, force: true })
    try {
      await fs.cp(this.options.bundledRuntimeDir, stagedDir, { recursive: true, force: true })
      if (!existsSync(join(stagedDir, 'python.exe'))) {
        throw new Error('复制随包 Python 失败：目标目录中没有 python.exe。')
      }
      await fs.rm(this.installDir, { recursive: true, force: true })
      await fs.rename(stagedDir, this.installDir)
    } catch (error) {
      await fs.rm(stagedDir, { recursive: true, force: true }).catch(() => undefined)
      throw error
    }
  }

  private enableEmbeddedSitePackages(): void {
    const sitePackagesDir = join(this.installDir, 'Lib', 'site-packages')
    if (!existsSync(this.installDir)) {
      throw new Error(`Python 运行目录不存在：${this.installDir}`)
    }
    if (!existsSync(sitePackagesDir)) {
      mkdirSync(sitePackagesDir, { recursive: true })
      writeFileSync(join(sitePackagesDir, '.keep'), '', 'utf8')
    }
    const pthFiles = readdirSync(this.installDir).filter((name) => /^python(?:\d+)?\._pth$/i.test(name))
    if (!pthFiles.length) {
      throw new Error('随包 Python 缺少 ._pth 配置文件，无法加载已安装的依赖。')
    }

    for (const name of pthFiles) {
      const path = join(this.installDir, name)
      const lines = readFileSync(path, 'utf8').split(/\r?\n/)
      const hasSitePackages = lines.some((line) => /^\s*lib[\\/]site-packages\s*$/i.test(line))
      const siteLines = lines.filter((line) => !/^\s*import\s+site\s*$/i.test(line))
      if (!hasSitePackages) siteLines.push('Lib/site-packages')
      siteLines.push('import site')
      writeFileSync(path, `${siteLines.join('\n').replace(/\n+$/, '')}\n`, 'utf8')
    }
  }

  private hasReadyMarker(): boolean {
    try {
      const marker = JSON.parse(readFileSync(this.readyMarkerPath, 'utf8')) as {
        schemaVersion?: number
        torchMode?: string
      }
      if (marker.schemaVersion !== RUNTIME_SCHEMA_VERSION || marker.torchMode !== 'cpu') return false
      const probe = spawnSync(
        this.pythonPath,
        [
          '-c',
          'import importlib.util, sys; names=("fastapi", "uvicorn", "cv2", "torch", "torchvision", "ultralytics"); missing=[name for name in names if importlib.util.find_spec(name) is None]; print("missing=" + ",".join(missing)); sys.exit(bool(missing))'
        ],
        {
          cwd: this.options.backendDir,
          encoding: 'utf8',
          timeout: 30_000,
          windowsHide: true,
          stdio: ['ignore', 'pipe', 'pipe']
        }
      )
      return probe.status === 0
    } catch {
      return false
    }
  }

  private async ensurePip(): Promise<void> {
    const result = spawnSync(this.pythonPath, ['-m', 'pip', '--version'], {
      cwd: this.options.backendDir,
      encoding: 'utf8',
      timeout: 30_000,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe']
    })
    if (result.status === 0) return

    this.update({
      phase: 'initializing',
      step: '2/5 · 准备安装工具',
      message: '正在为随包 Python 安装 pip…'
    })
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 60_000)
    let bootstrapPath = ''
    try {
      const response = await fetch(PIP_BOOTSTRAP_URL, { signal: controller.signal })
      if (!response.ok) throw new Error(`下载 pip 引导程序失败：HTTP ${response.status}`)
      bootstrapPath = join(this.options.userDataDir, 'get-pip.py')
      writeFileSync(bootstrapPath, Buffer.from(await response.arrayBuffer()))
      await this.runInstallerProcess(
        this.pythonPath,
        [bootstrapPath, '--disable-pip-version-check'],
        '2/5 · 准备安装工具',
        '正在安装 pip…'
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      throw new Error(`无法准备 pip。请检查网络连接后重试。${message ? `\n${message}` : ''}`)
    } finally {
      clearTimeout(timeout)
      if (bootstrapPath) await fs.rm(bootstrapPath, { force: true }).catch(() => undefined)
    }
  }

  private async ensureCpuTorch(): Promise<void> {
    const cpuCheck = spawnSync(
      this.pythonPath,
      [
        '-c',
        'import torch, torchvision; assert torch.version.cuda is None; print(torch.__version__, torchvision.__version__)'
      ],
      {
        cwd: this.options.backendDir,
        encoding: 'utf8',
        timeout: 60_000,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
      }
    )
    if (cpuCheck.status === 0) return

    const args = [
      '-m',
      'pip',
      'install',
      '--disable-pip-version-check',
      '--no-input',
      '--progress-bar',
      'on',
      '--index-url',
      PYTORCH_CPU_INDEX,
      '--extra-index-url',
      PYPI_INDEX,
      '--force-reinstall'
    ]
    args.push('torch>=2.4.0', 'torchvision>=0.19.0')
    await this.runInstallerProcess(this.pythonPath, args, '3/5 · 安装 CPU 推理环境', '正在下载 CPU 版 PyTorch…')
  }

  private runPipInstall(requirements: string[]): Promise<void> {
    return this.runInstallerProcess(
      this.pythonPath,
      ['-m', 'pip', 'install', '--disable-pip-version-check', '--no-input', '--progress-bar', 'on', ...requirements],
      this.status.step,
      this.status.message
    )
  }

  private runInstallerProcess(
    executable: string,
    args: string[],
    step: string,
    initialMessage: string
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const child = spawn(executable, args, {
        cwd: this.options.backendDir,
        env: {
          ...process.env,
          PYTHONUTF8: '1',
          PIP_DISABLE_PIP_VERSION_CHECK: '1'
        },
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
      })
      this.process = child
      const decoders = [new StringDecoder('utf8'), new StringDecoder('utf8')]
      const tails = ['', '']
      let settled = false

      const fail = (error: Error) => {
        if (settled) return
        settled = true
        this.process = null
        reject(error)
      }
      const consume = (index: number, chunk: Buffer) => {
        const combined = tails[index] + decoders[index].write(chunk)
        const lines = combined.split(/[\r\n]+/)
        tails[index] = lines.pop() || ''
        for (const line of lines) this.recordOutput(line, step, initialMessage)
      }

      child.stdout?.on('data', (chunk: Buffer) => consume(0, chunk))
      child.stderr?.on('data', (chunk: Buffer) => consume(1, chunk))
      child.on('error', (error) => fail(error))
      child.on('close', (code, signal) => {
        for (let i = 0; i < decoders.length; i += 1) {
          const finalText = tails[i] + decoders[i].end()
          if (finalText.trim()) this.recordOutput(finalText, step, initialMessage)
        }
        if (settled) return
        settled = true
        this.process = null
        if (code === 0) {
          resolve()
          return
        }
        const reason = code === null ? `信号 ${signal || 'unknown'}` : `退出码 ${code}`
        const recent = this.details.slice(-8).join('\n')
        reject(new Error(`安装命令失败（${reason}）。${recent ? `\n${recent}` : ''}`))
      })
    })
  }

  private recordOutput(raw: string, step: string, fallbackMessage: string): void {
    const line = raw.replace(/\x1B\[[0-9;?]*[ -/]*[@-~]/g, '').trim()
    if (!line) return
    const detail = line.slice(0, 600)
    this.addDetail(detail)
    this.update({
      phase: 'initializing',
      step,
      message: detail || fallbackMessage
    })
  }

  private addDetail(message: string): void {
    const value = message.trim().slice(0, 1000)
    if (!value) return
    this.details.push(value)
    this.details = this.details.slice(-40)
  }

  private update(patch: Partial<RuntimeSetupStatus>): void {
    this.status = {
      ...this.status,
      ...patch,
      details: patch.details ? [...patch.details] : [...this.details]
    }
    this.emit('status', this.getStatus())
  }
}
