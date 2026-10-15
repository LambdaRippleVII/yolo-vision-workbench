/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

interface YoloStudioBridge {
  getBackendStatus: () => Promise<{
    status: string
    restarts: number
    port: number
    host: string
    message?: string
    reusedPid?: number
  }>
  getWsUrl: () => Promise<string>
  restartBackend: () => Promise<{
    status: string
    restarts: number
    port: number
    host: string
    message?: string
    reusedPid?: number
  }>
  getRuntimeSetupStatus?: () => Promise<{
    managed: boolean
    phase: 'initializing' | 'ready' | 'failed'
    step: string
    message: string
    error: string
    details: string[]
  }>
  retryRuntimeSetup?: () => Promise<{
    managed: boolean
    phase: 'initializing' | 'ready' | 'failed'
    step: string
    message: string
    error: string
    details: string[]
  }>
  onRuntimeSetupStatus?: (
    cb: (status: {
      managed: boolean
      phase: 'initializing' | 'ready' | 'failed'
      step: string
      message: string
      error: string
      details: string[]
    }) => void
  ) => () => void
  onBackendStatus: (
    cb: (s: {
      status: string
      restarts: number
      port: number
      host: string
      message?: string
      reusedPid?: number
    }) => void
  ) => () => void
  onBackendLog: (cb: (e: { level: string; source: string; message: string }) => void) => () => void
  onMenuAction?: (cb: (payload: { action: string }) => void) => () => void
  openCameraWindow?: () => Promise<void>
  setAlwaysOnTop?: (flag: boolean) => Promise<void>
  selectImage?: () => Promise<string | null>
  selectModelFile?: () => Promise<string | null>
  selectVideo?: () => Promise<string | null>
  saveVideo?: (defaultName?: string) => Promise<string | null>
  saveImage?: (defaultName?: string) => Promise<string | null>
  selectFolder?: () => Promise<string | null>
  mediaUrl?: (path: string) => Promise<string | null>
  readImageBase64?: (path: string) => Promise<string | null>
  writeTempImage?: (payload: { name?: string; base64?: string; dataUrl?: string }) => Promise<string | null>
  getPathForFile?: (file: File) => string
}

interface Window {
  yoloStudio?: YoloStudioBridge
}
