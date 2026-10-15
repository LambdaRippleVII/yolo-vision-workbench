/**
 * Preload: expose a minimal, typed bridge to the renderer.
 */
import { contextBridge, ipcRenderer, webUtils } from 'electron'

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
}

const api = {
  getBackendStatus: (): Promise<BackendStatus> => ipcRenderer.invoke('backend:getStatus'),
  getWsUrl: (): Promise<string> => ipcRenderer.invoke('backend:getWsUrl'),
  restartBackend: (): Promise<BackendStatus> => ipcRenderer.invoke('backend:restart'),
  getRuntimeSetupStatus: (): Promise<RuntimeSetupStatus> => ipcRenderer.invoke('runtime:getStatus'),
  retryRuntimeSetup: (): Promise<RuntimeSetupStatus> => ipcRenderer.invoke('runtime:retry'),
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
  openCameraWindow: (): Promise<void> => ipcRenderer.invoke('window:openCamera'),
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
  /** Resolve absolute path for a dropped File (works for files and folders). */
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
