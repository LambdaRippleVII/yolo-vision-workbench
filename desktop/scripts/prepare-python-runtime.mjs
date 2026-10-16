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
// pip 在 Windows 上生成命令行入口时需要这些 distlib 启动器资源。
const DISTLIB_LAUNCHERS = ['t32.exe', 't64.exe', 't64-arm.exe', 'w32.exe', 'w64.exe', 'w64-arm.exe']

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

async function ensureDistlibLaunchers() {
  const distlibDir = resolve(runtimeDir, 'Lib', 'site-packages', 'pip', '_vendor', 'distlib')
  const required = process.arch === 'arm64' ? ['t64-arm.exe', 'w64-arm.exe'] : process.arch === 'ia32' ? ['t32.exe', 'w32.exe'] : ['t64.exe', 'w64.exe']
  if (required.every((name) => existsSync(resolve(distlibDir, name)))) return

  console.log('随包 Python 缺少 pip 的 Windows 启动器，正在从 pip wheel 修复…')
  const repairDir = resolve(tmpdir(), `yolo-vision-workbench-pip-repair-${process.pid}`)
  mkdirSync(repairDir, { recursive: true })
  try {
    // 只下载 wheel，不执行安装，因此不会触发当前缺失启动器的问题。
    runPython([
      '-m',
      'pip',
      'download',
      '--disable-pip-version-check',
      '--no-input',
      '--no-cache-dir',
      '--no-deps',
      '--only-binary=:all:',
      '--dest',
      repairDir,
      'pip'
    ])
    const wheel = readdirSync(repairDir).find((name) => /^pip-.*\.whl$/i.test(name))
    if (!wheel) throw new Error('没有找到已下载的 pip wheel。')
    const extractScript = [
      'import pathlib, sys, zipfile',
      'wheel = pathlib.Path(sys.argv[1])',
      'target = pathlib.Path(sys.argv[2])',
      'target.mkdir(parents=True, exist_ok=True)',
      'with zipfile.ZipFile(wheel) as archive:',
      '    names = set(archive.namelist())',
      `    for name in ${JSON.stringify(DISTLIB_LAUNCHERS)}:`,
      "        source = 'pip/_vendor/distlib/' + name",
      '        if source in names: (target / name).write_bytes(archive.read(source))'
    ].join('\n')
    runPython(['-c', extractScript, resolve(repairDir, wheel), distlibDir])
    const missing = required.filter((name) => !existsSync(resolve(distlibDir, name)))
    if (missing.length) throw new Error(`pip wheel 中仍缺少启动器：${missing.join(', ')}`)
  } finally {
    rmSync(repairDir, { recursive: true, force: true })
  }
}

enableEmbeddedSitePackages()
await ensurePip()
await ensureDistlibLaunchers()

console.log('随包 Python 已准备好；后端依赖和 YOLO CPU 推理组件将在软件首次启动时安装到用户目录。')
