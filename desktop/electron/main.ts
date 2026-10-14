/**
 * Electron main process entry.
 * 产品名：YOLO Vision Workbench
 */
import { app, BrowserWindow, dialog, ipcMain, Menu, shell, MenuItemConstructorOptions } from 'electron'
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs'
import { join, resolve, basename } from 'path'
import { ProcessSupervisor } from './backend/supervisor'

const PRODUCT_NAME = 'YOLO Vision Workbench'

const HOST = process.env.YOLO_STUDIO_HOST || '127.0.0.1'
const PORT = Number(process.env.YOLO_STUDIO_PORT || 8765)
const ATTACH = process.env.YOLO_STUDIO_ATTACH === '1'

function logMain(message: string): void {
  try {
    const dir = resolve(repoRoot(), 'logs')
    mkdirSync(dir, { recursive: true })
    appendFileSync(join(dir, 'electron-main.log'), `${new Date().toISOString()} ${message}\n`)
  } catch {
    /* ignore logging failures */
  }
}

function repoRoot(): string {
  // Packaged: use resources dir (contains backend/, models/)
  const res = process.resourcesPath
  if (res && existsSync(join(res, 'backend'))) {
    return res
  }
  // Dev: desktop/ -> project root
  const desktopDir = app.getAppPath()
  return resolve(desktopDir, '..')
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

const supervisor = new ProcessSupervisor({
  rootDir: repoRoot(),
  host: HOST,
  port: PORT,
  attachMode: ATTACH,
  autoPort: true
})

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
  await supervisor.stop()
  await supervisor.start()
  return supervisor.getStatus()
})

ipcMain.handle('dialog:selectModelFile', async () => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return null
  const result = await dialog.showOpenDialog(win, {
    title: '选择模型文件',
    properties: ['openFile'],
    filters: [
      { name: '模型', extensions: ['pt', 'onnx', 'engine', 'rknn'] }
    ]
  })
  if (result.canceled || !result.filePaths.length) return null
  return result.filePaths[0]
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
      { name: '视频', extensions: ['mp4', 'avi', 'mov', 'mkv', 'webm'] }
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

/** Save pasted/dropped clipboard image bytes to a temp file with a real absolute path. */
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

app.whenReady().then(async () => {
  app.setName(PRODUCT_NAME)
  buildAppMenu()
  logMain('app ready, starting supervisor')
  createWindow()

  try {
    await supervisor.start()
    logMain(`supervisor started status=${JSON.stringify(supervisor.getStatus())}`)
  } catch (err) {
    logMain(`failed to start backend: ${String(err)}`)
    console.error('failed to start backend', err)
  }

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
  void supervisor.stop()
})
