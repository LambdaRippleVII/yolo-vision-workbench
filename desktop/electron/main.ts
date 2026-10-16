/** Electron 主进程入口：准备运行环境、管理本地后端并创建应用窗口。 */
import { app, BrowserWindow, dialog, ipcMain, Menu, shell, MenuItemConstructorOptions } from 'electron'
import { appendFileSync, copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'fs'
import { pathToFileURL } from 'url'
import { join, resolve, basename } from 'path'
import { ProcessSupervisor } from './backend/supervisor'
import { RuntimeSetup, type RuntimeSetupStatus } from './runtime-setup'
import { DEFAULT_PACKAGE_SOURCE, type PackageSourceSelection } from '../shared/package-source'

// 窗口标题、系统菜单和应用元数据共用的产品名称。
const PRODUCT_NAME = 'YOLO 视觉工作台'

function appIconPath(): string {
  return app.isPackaged
    ? join(process.resourcesPath, 'app-icon.ico')
    : resolve(app.getAppPath(), 'build', 'icon.ico')
}

// 本地后端绑定地址，默认仅监听回环接口。
const HOST = process.env.YOLO_STUDIO_HOST || '127.0.0.1'
// 本地 WebSocket 后端优先使用的端口。
const PORT = Number(process.env.YOLO_STUDIO_PORT || 8765)
// 开发调试开关：连接已有后端进程，而不由应用另行启动。
const ATTACH = process.env.YOLO_STUDIO_ATTACH === '1'

function logMain(message: string): void {
  try {
    const dir = app.isPackaged ? join(app.getPath('userData'), 'logs') : resolve(repoRoot(), 'logs')
    mkdirSync(dir, { recursive: true })
    appendFileSync(join(dir, 'electron-main.log'), `${new Date().toISOString()} ${message}\n`)
  } catch {
    /* 日志写入失败不应阻断应用启动和后端管理。 */
  }
}

function repoRoot(): string {
  // 打包运行时使用包含 backend 和 models 的 resources 目录。
  const res = process.resourcesPath
  if (res && existsSync(join(res, 'backend'))) {
    return res
  }
  // 开发运行时从 desktop 目录回到仓库根目录。
  const desktopDir = app.getAppPath()
  return resolve(desktopDir, '..')
}

function copyMissingFiles(sourceDir: string, targetDir: string): void {
  if (!existsSync(sourceDir)) return
  mkdirSync(targetDir, { recursive: true })
  for (const entry of readdirSync(sourceDir, { withFileTypes: true })) {
    const source = join(sourceDir, entry.name)
    const target = join(targetDir, entry.name)
    if (entry.isDirectory()) {
      copyMissingFiles(source, target)
    } else if (entry.isFile() && !existsSync(target)) {
      copyFileSync(source, target)
    }
  }
}

function preparePackagedData(): void {
  if (!app.isPackaged) return

  const userDataDir = app.getPath('userData')
  const modelsDir = resolve(process.env.YOLO_STUDIO_MODELS_DIR || join(userDataDir, 'models'))
  const projectsDir = resolve(process.env.YOLO_STUDIO_PROJECTS_DIR || join(userDataDir, 'projects'))
  const logsDir = resolve(process.env.YOLO_STUDIO_LOGS_DIR || join(userDataDir, 'logs'))

  copyMissingFiles(join(process.resourcesPath, 'models'), modelsDir)
  copyMissingFiles(join(process.resourcesPath, 'projects'), projectsDir)
  mkdirSync(projectsDir, { recursive: true })
  mkdirSync(logsDir, { recursive: true })
  process.env.YOLO_STUDIO_MODELS_DIR = modelsDir
  process.env.YOLO_STUDIO_PROJECTS_DIR = projectsDir
  process.env.YOLO_STUDIO_LOGS_DIR = logsDir
}

/** 系统级应用菜单（中文） */
function buildAppMenu(): void {
  const isMac = process.platform === 'darwin'

  const template: MenuItemConstructorOptions[] = []
  if (isMac) {
    template.push({
      label: PRODUCT_NAME,
      submenu: [
        { role: 'about', label: `关于 ${PRODUCT_NAME}` },
        { type: 'separator' },
        { role: 'services', label: '服务' },
        { type: 'separator' },
        { role: 'hide', label: `隐藏 ${PRODUCT_NAME}` },
        { role: 'hideOthers', label: '隐藏其他' },
        { role: 'unhide', label: '全部显示' },
        { type: 'separator' },
        { role: 'quit', label: `退出 ${PRODUCT_NAME}` }
      ]
    })
  }

  template.push(
    {
      label: '文件',
      submenu: [
        {
          label: '打开项目…',
          accelerator: 'CmdOrCtrl+O',
          id: 'file.openProject',
          click: () => {
            const win = BrowserWindow.getAllWindows()[0]
            win?.webContents.send('menu:action', { action: 'openProject' })
          }
        },
        {
          label: '新建项目…',
          accelerator: 'CmdOrCtrl+N',
          id: 'file.newProject',
          click: () => {
            const win = BrowserWindow.getAllWindows()[0]
            win?.webContents.send('menu:action', { action: 'newProject' })
          }
        },
        { type: 'separator' },
        isMac ? { role: 'close', label: '关闭窗口' } : { role: 'quit', label: '退出' }
      ]
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' }
      ]
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '重新加载' },
        { role: 'forceReload', label: '强制重新加载' },
        { type: 'separator' },
        { role: 'resetZoom', label: '实际大小' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' },
        { type: 'separator' },
        { role: 'toggleDevTools', label: '开发者工具' }
      ]
    },
    {
      label: '窗口',
      submenu: isMac
        ? [
            { role: 'minimize', label: '最小化' },
            { role: 'zoom', label: '缩放' },
            { type: 'separator' },
            { role: 'front', label: '前置全部窗口' }
          ]
        : [
            { role: 'minimize', label: '最小化' },
            { role: 'close', label: '关闭窗口' }
          ]
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '使用说明',
          click: () => {
            logMain('help: docs opened')
          }
        },
        {
          label: '检查后端服务状态',
          click: () => {
            const win = BrowserWindow.getAllWindows()[0]
            win?.webContents.send('menu:action', { action: 'health' })
          }
        },
        { type: 'separator' },
        {
          label: `关于 ${PRODUCT_NAME}`,
          click: () => {
            const win = BrowserWindow.getAllWindows()[0]
            win?.webContents.send('menu:action', { action: 'about' })
          }
        }
      ]
    }
  )

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// 管理后端进程、端口选择、健康检查和异常重启的唯一协调器。
const supervisor = new ProcessSupervisor({
  rootDir: repoRoot(),
  host: HOST,
  port: PORT,
  version: app.getVersion(),
  attachMode: ATTACH,
  autoPort: true
})

// 当前应用实例负责的 Python 环境初始化器。
let runtimeSetup: RuntimeSetup | null = null
// 共享正在进行的后端启动请求，防止菜单重启与启动流程相互覆盖。
let backendStartPromise: Promise<void> | null = null

// 当前主窗口拥有的摄像头独立窗口；用于把关闭状态准确同步回发起页面。
let cameraPopout: {
  win: BrowserWindow
  owner: BrowserWindow | null
  streamId: string
} | null = null

function notifyCameraPopoutState(
  owner: BrowserWindow | null,
  state: { open: boolean; streamId: string }
): void {
  if (owner && !owner.isDestroyed()) owner.webContents.send('window:cameraState', state)
}

function currentRuntimeStatus(): RuntimeSetupStatus {
  return (
    runtimeSetup?.getStatus() ?? {
      managed: app.isPackaged,
      phase: app.isPackaged ? 'initializing' : 'ready',
      step: app.isPackaged ? '准备运行环境' : '开发环境',
      message: app.isPackaged ? '正在检查随包 Python 运行环境…' : '开发环境由当前 Python 配置提供。',
      error: '',
      details: [],
      packageSource: { ...DEFAULT_PACKAGE_SOURCE }
    }
  )
}

function initializeRuntimeSetup(): void {
  const userDataDir = app.getPath('userData')
  // 打包版使用随安装包提供的 Python；开发版沿用用户配置的解释器。
  runtimeSetup = new RuntimeSetup({
    managed: app.isPackaged,
    bundledRuntimeDir: join(process.resourcesPath || '', 'python-embed', 'runtime'),
    userDataDir,
    backendDir: join(repoRoot(), 'backend')
  })
  runtimeSetup.on('status', (status: RuntimeSetupStatus) => {
    logMain(`[runtime] ${status.phase} · ${status.step} · ${status.message}`)
    const win = BrowserWindow.getAllWindows()[0]
    win?.webContents.send('runtime:status', status)
  })
  supervisor.setPythonPath(
    app.isPackaged ? join(userDataDir, 'python-runtime', 'python.exe') : undefined
  )
}

async function startBackendWithRuntime(restart = false): Promise<void> {
  // 重复触发时复用同一个 Promise，确保初始化和服务启动只执行一份。
  if (backendStartPromise) return backendStartPromise

  backendStartPromise = (async () => {
    try {
      // 按“准备用户数据 → 初始化 Python 依赖 → 启动服务 → 验证状态”的顺序完成启动。
      if (restart) await supervisor.stop()
      preparePackagedData()
      if (runtimeSetup) await runtimeSetup.initialize()
      supervisor.setPythonPath(
        app.isPackaged
          ? join(app.getPath('userData'), 'python-runtime', 'python.exe')
          : undefined
      )
      await supervisor.start()
      const status = supervisor.getStatus()
      if (status.status !== 'ready' && status.status !== 'reused') {
        throw new Error(status.message || '本地服务启动失败，请查看日志后重试。')
      }
      await runtimeSetup?.markReady('Python 推理环境和本地服务已就绪。')
      logMain(`supervisor started status=${JSON.stringify(status)}`)
    } catch (error) {
      await runtimeSetup?.markFailed(error)
      logMain(`failed to prepare runtime or start backend: ${String(error)}`)
      console.error('failed to prepare runtime or start backend', error)
      throw error
    }
  })().finally(() => {
    backendStartPromise = null
  })

  return backendStartPromise
}

// 把后端日志转发到文件与渲染进程，供界面状态区展示诊断信息。
supervisor.on('log', (entry: { level: string; source: string; message: string }) => {
  logMain(`[${entry.level}] ${entry.source}: ${entry.message}`)
  const win = BrowserWindow.getAllWindows()[0]
  win?.webContents.send('backend:log', entry)
})

supervisor.on('status', (status) => {
  const win = BrowserWindow.getAllWindows()[0]
  win?.webContents.send('backend:status', status)
})

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1100,
    minHeight: 700,
    resizable: true,
    maximizable: true,
    fullscreenable: true,
    title: PRODUCT_NAME,
    icon: appIconPath(),
    show: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  win.webContents.on('before-input-event', (_event, input) => {
    if (input.type === 'keyDown' && input.key === 'F11') {
      win.setFullScreen(!win.isFullScreen())
    }
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    void win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

ipcMain.handle('backend:getStatus', () => supervisor.getStatus())
ipcMain.handle('backend:getWsUrl', () => supervisor.getWsUrl())
ipcMain.handle('backend:restart', async () => {
  await startBackendWithRuntime(true)
  return supervisor.getStatus()
})
ipcMain.handle('runtime:getStatus', () => currentRuntimeStatus())
ipcMain.handle('runtime:retry', async (_event, packageSource?: PackageSourceSelection) => {
  try {
    if (packageSource) await runtimeSetup?.setPackageSource(packageSource)
  } catch (error) {
    // 镜像配置写入失败时，直接更新初始化错误，避免界面继续显示旧错误。
    await runtimeSetup?.markFailed(error)
    return currentRuntimeStatus()
  }

  try {
    await startBackendWithRuntime(true)
  } catch {
    // startBackendWithRuntime 会把初始化或服务启动错误写入运行时状态。
  }
  return currentRuntimeStatus()
})

ipcMain.handle('dialog:selectModelFile', async () => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showOpenDialog(win, {
    title: '选择模型文件',
    properties: ['openFile'],
    filters: [
      { name: '模型', extensions: ['pt', 'onnx', 'engine', 'rknn', 'torchscript'] }
    ]
  })
  if (result.canceled || !result.filePaths.length) return null
  return result.filePaths[0]
})

ipcMain.handle('window:openCamera', async (event, streamIdValue: string) => {
  const streamId = String(streamIdValue || '').trim()
  if (!streamId) throw new Error('没有可分离的摄像头画面，请先打开摄像头。')

  const owner = BrowserWindow.fromWebContents(event.sender)
  if (cameraPopout && !cameraPopout.win.isDestroyed()) {
    if (cameraPopout.owner === owner && cameraPopout.streamId === streamId) {
      cameraPopout.win.focus()
      notifyCameraPopoutState(owner, { open: true, streamId })
      return
    }
    const previous = cameraPopout
    cameraPopout = null
    notifyCameraPopoutState(previous.owner, { open: false, streamId: previous.streamId })
    previous.win.close()
  }

  const win = new BrowserWindow({
    width: 960,
    height: 640,
    minWidth: 360,
    minHeight: 240,
    resizable: true,
    maximizable: true,
    fullscreenable: true,
    parent: owner && !owner.isDestroyed() ? owner : undefined,
    title: '摄像头预览',
    icon: appIconPath(),
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })
  const record = { win, owner, streamId }
  cameraPopout = record
  win.on('closed', () => {
    notifyCameraPopoutState(record.owner, { open: false, streamId: record.streamId })
    if (cameraPopout === record) cameraPopout = null
  })
  const base =
    process.env.ELECTRON_RENDERER_URL ||
    `file://${join(__dirname, '../renderer/index.html')}`
  try {
    await win.loadURL(`${base}#/camera-popout?stream_id=${encodeURIComponent(streamId)}`)
    notifyCameraPopoutState(owner, { open: true, streamId })
  } catch (error) {
    if (!win.isDestroyed()) win.close()
    throw error
  }
})

ipcMain.handle('window:setAlwaysOnTop', (event, flag: boolean) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  win?.setAlwaysOnTop(Boolean(flag))
})

ipcMain.handle('window:closeCamera', (event) => {
  const owner = BrowserWindow.fromWebContents(event.sender)
  if (cameraPopout?.owner === owner && !cameraPopout.win.isDestroyed()) cameraPopout.win.close()
})

ipcMain.handle('fs:mediaUrl', (_e, filePath: string) => {
  try {
    return pathToFileURL(String(filePath)).href
  } catch {
    return null
  }
})

ipcMain.handle('dialog:selectImage', async () => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showOpenDialog(win, {
    title: '选择图片',
    properties: ['openFile'],
    filters: [
      { name: '图片', extensions: ['jpg', 'jpeg', 'png', 'bmp', 'webp'] }
    ]
  })
  if (result.canceled || !result.filePaths.length) return null
  return result.filePaths[0]
})

ipcMain.handle('dialog:selectVideo', async () => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showOpenDialog(win, {
    title: '选择视频',
    properties: ['openFile'],
    filters: [
      { name: '视频', extensions: ['mp4', 'm4v', 'avi', 'mov', 'mkv', 'webm', 'flv', '3gp'] }
    ]
  })
  if (result.canceled || !result.filePaths.length) return null
  return result.filePaths[0]
})

ipcMain.handle('dialog:saveVideo', async (_e, defaultName?: string) => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showSaveDialog(win, {
    title: '导出视频',
    defaultPath: String(defaultName || 'export.mp4'),
    filters: [{ name: '视频', extensions: ['mp4'] }]
  })
  if (result.canceled || !result.filePath) return null
  return result.filePath
})

ipcMain.handle('dialog:saveImage', async (_e, defaultName?: string) => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showSaveDialog(win, {
    title: '保存识别图',
    defaultPath: String(defaultName || 'result.jpg'),
    filters: [
      { name: '图片', extensions: ['jpg', 'jpeg', 'png'] }
    ]
  })
  if (result.canceled || !result.filePath) return null
  return result.filePath
})

ipcMain.handle('dialog:selectFolder', async () => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showOpenDialog(win, {
    title: '选择文件夹',
    properties: ['openDirectory']
  })
  if (result.canceled || !result.filePaths.length) return null
  return result.filePaths[0]
})

ipcMain.handle('fs:readImageBase64', (_e, filePath: string) => {
  try {
    const buf = readFileSync(String(filePath))
    const ext = String(filePath).split('.').pop()?.toLowerCase() || 'png'
    const mime = ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : ext === 'webp' ? 'image/webp' : 'image/png'
    return `data:${mime};base64,${buf.toString('base64')}`
  } catch {
    return null
  }
})

/** 将粘贴或拖入的剪贴板图片字节保存为带真实绝对路径的临时文件。 */
ipcMain.handle(
  'fs:writeTempImage',
  (_e, payload: { name?: string; base64?: string; dataUrl?: string }) => {
    try {
      let name = String(payload?.name || 'paste.png')
      name = name.replace(/[\\/:*?"<>|]/g, '_')
      if (!/\.[a-z0-9]+$/i.test(name)) name += '.png'
      const dir = join(app.getPath('temp'), 'yolo-vision-workbench')
      mkdirSync(dir, { recursive: true })
      const out = join(dir, `${Date.now()}_${basename(name)}`)
      let b64 = payload?.base64 || ''
      if (!b64 && payload?.dataUrl) {
        b64 = String(payload.dataUrl).replace(/^data:[^,]+,/, '')
      }
      if (!b64) return null
      writeFileSync(out, Buffer.from(b64, 'base64'))
      return out
    } catch {
      return null
    }
  }
)

// Electron 就绪后先建立状态转发和窗口，再后台执行依赖初始化与服务启动。
app.whenReady().then(async () => {
  app.setName(PRODUCT_NAME)
  buildAppMenu()
  initializeRuntimeSetup()
  logMain('app ready, starting supervisor')
  createWindow()

  void startBackendWithRuntime().catch(() => undefined)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  runtimeSetup?.terminate()
  void supervisor.stop()
})
