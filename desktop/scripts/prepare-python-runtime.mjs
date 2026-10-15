import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve, join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'

const desktopDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const projectDir = resolve(desktopDir, '..')
const backendDir = resolve(projectDir, 'backend')
const runtimeDir = resolve(desktopDir, 'vendor', 'python-embed', 'runtime')
const legacyRuntimeDir = resolve(desktopDir, 'release', 'python-embed', 'runtime')
const pythonPath = resolve(runtimeDir, 'python.exe')

if (!existsSync(runtimeDir) && existsSync(legacyRuntimeDir)) {
  mkdirSync(dirname(runtimeDir), { recursive: true })
  cpSync(legacyRuntimeDir, runtimeDir, { recursive: true })
  console.log('已将旧位置的 Python 运行时复制到 desktop/vendor/python-embed/runtime。')
}

if (!existsSync(pythonPath)) {
  throw new Error(
    `缺少随包 Python 运行时：${pythonPath}。请先准备 Windows x64 Python 3.11+ embeddable runtime，再运行 npm run dist。`
  )
}

function runPython(args) {
  const result = spawnSync(pythonPath, args, {
    cwd: backendDir,
    stdio: 'inherit',
    windowsHide: true
  })
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`准备随包 Python 运行时失败（退出码 ${result.status ?? 'unknown'}）。`)
  }
}

runPython([
  '-c',
  'import struct, sys; assert sys.version_info >= (3, 11), f"Python 3.11+ is required, found {sys.version.split()[0]}"; assert struct.calcsize("P") == 8, "A 64-bit Python runtime is required"'
])

function enableEmbeddedSitePackages() {
  mkdirSync(join(runtimeDir, 'Lib', 'site-packages'), { recursive: true })
  const pthFiles = readdirSync(runtimeDir).filter((name) => /^python(?:\d+)?\._pth$/i.test(name))
  for (const name of pthFiles) {
    const path = resolve(runtimeDir, name)
    const lines = readFileSync(path, 'utf8').split(/\r?\n/)
    const hasSitePackages = lines.some((line) => /^\s*lib[\\/]site-packages\s*$/i.test(line))
    const siteLines = lines.filter((line) => !/^\s*import\s+site\s*$/i.test(line))
    if (!hasSitePackages) siteLines.push('Lib/site-packages')
    siteLines.push('import site')
    writeFileSync(path, siteLines.join('\n').replace(/\n+$/, '\n'), 'utf8')
  }
}

async function ensurePip() {
  const result = spawnSync(pythonPath, ['-m', 'pip', '--version'], {
    cwd: backendDir,
    encoding: 'utf8',
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  })
  if (result.status === 0) return

  console.log('随包 Python 尚未安装 pip，正在从 PyPA 获取引导脚本…')
  const response = await fetch('https://bootstrap.pypa.io/get-pip.py')
  if (!response.ok) throw new Error(`下载 pip 引导脚本失败：HTTP ${response.status}`)
  const bootstrapPath = resolve(tmpdir(), `yolo-vision-workbench-get-pip-${process.pid}.py`)
  try {
    writeFileSync(bootstrapPath, Buffer.from(await response.arrayBuffer()))
    runPython([bootstrapPath, '--disable-pip-version-check'])
    runPython(['-m', 'pip', '--version'])
  } finally {
    rmSync(bootstrapPath, { force: true })
  }
}

enableEmbeddedSitePackages()
await ensurePip()

console.log('随包 Python 已准备好；后端依赖和 YOLO CPU 推理组件将在软件首次启动时安装到用户目录。')
