/** 通过受限且有类型的 IPC 接口向渲染进程暴露桌面能力。 */
import { contextBridge, ipcRenderer, webUtils } from 'electron'
import type { PackageSourceSelection } from '../shared/package-source'

export interface BackendStatus {
  status: string
  restarts: number
  port: number
  host: string
  message?: string
  reusedPid?: number
}

export interface BackendLogEntry {
  level: string
  source: string
  message: string
}

export interface RuntimeSetupStatus {
  managed: boolean
  phase: 'initializing' | 'ready' | 'failed'
  step: string
  message: string
  error: string
  details: string[]
  packageSource: PackageSourceSelection
}

// 仅公开界面实际需要的 IPC 方法，避免把 Electron 原始对象暴露给页面。
const api = {
  getBackendStatus: (): Promise<BackendStatus> => ipcRenderer.invoke('backend:getStatus'),
  getWsUrl: (): Promise<string> => ipcRenderer.invoke('backend:getWsUrl'),
  restartBackend: (): Promise<BackendStatus> => ipcRenderer.invoke('backend:restart'),
  getRuntimeSetupStatus: (): Promise<RuntimeSetupStatus> => ipcRenderer.invoke('runtime:getStatus'),
  retryRuntimeSetup: (source: PackageSourceSelection): Promise<RuntimeSetupStatus> =>
    ipcRenderer.invoke('runtime:retry', source),
  onRuntimeSetupStatus: (cb: (status: RuntimeSetupStatus) => void): (() => void) => {
    const listener = (_: unknown, status: RuntimeSetupStatus) => cb(status)
    ipcRenderer.on('runtime:status', listener)
    return () => ipcRenderer.removeListener('runtime:status', listener)
  },
  onBackendStatus: (cb: (status: BackendStatus) => void): (() => void) => {
    const listener = (_: unknown, status: BackendStatus) => cb(status)
    ipcRenderer.on('backend:status', listener)
    return () => ipcRenderer.removeListener('backend:status', listener)
  },
  onBackendLog: (cb: (entry: BackendLogEntry) => void): (() => void) => {
    const listener = (_: unknown, entry: BackendLogEntry) => cb(entry)
    ipcRenderer.on('backend:log', listener)
    return () => ipcRenderer.removeListener('backend:log', listener)
  },
  onMenuAction: (cb: (payload: { action: string }) => void): (() => void) => {
    const listener = (_: unknown, payload: { action: string }) => cb(payload)
    ipcRenderer.on('menu:action', listener)
    return () => ipcRenderer.removeListener('menu:action', listener)
  },
  openCameraWindow: (streamId: string): Promise<void> => ipcRenderer.invoke('window:openCamera', streamId),
  onCameraWindowState: (
    cb: (state: { open: boolean; streamId: string }) => void
  ): (() => void) => {
    const listener = (_event: unknown, state: { open: boolean; streamId: string }) => cb(state)
    ipcRenderer.on('window:cameraState', listener)
    return () => ipcRenderer.removeListener('window:cameraState', listener)
  },
  closeCameraWindow: (): Promise<void> => ipcRenderer.invoke('window:closeCamera'),
  setAlwaysOnTop: (flag: boolean): Promise<void> => ipcRenderer.invoke('window:setAlwaysOnTop', flag),
  selectImage: (): Promise<string | null> => ipcRenderer.invoke('dialog:selectImage'),
  selectModelFile: (): Promise<string | null> => ipcRenderer.invoke('dialog:selectModelFile'),
  selectVideo: (): Promise<string | null> => ipcRenderer.invoke('dialog:selectVideo'),
  saveVideo: (defaultName?: string): Promise<string | null> =>
    ipcRenderer.invoke('dialog:saveVideo', defaultName),
  saveImage: (defaultName?: string): Promise<string | null> =>
    ipcRenderer.invoke('dialog:saveImage', defaultName),
  selectFolder: (): Promise<string | null> => ipcRenderer.invoke('dialog:selectFolder'),
  mediaUrl: (filePath: string): Promise<string | null> => ipcRenderer.invoke('fs:mediaUrl', filePath),
  readImageBase64: (filePath: string): Promise<string | null> =>
    ipcRenderer.invoke('fs:readImageBase64', filePath),
  writeTempImage: (payload: { name?: string; base64?: string; dataUrl?: string }): Promise<string | null> =>
    ipcRenderer.invoke('fs:writeTempImage', payload),
  /** 解析拖入文件或文件夹的绝对路径。 */
  getPathForFile: (file: File): string => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return (file as File & { path?: string }).path || ''
    }
  }
}

contextBridge.exposeInMainWorld('yoloStudio', api)

export type YoloStudioApi = typeof api
