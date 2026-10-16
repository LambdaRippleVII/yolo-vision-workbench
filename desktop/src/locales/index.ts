/**
 * 轻量 i18n：默认 zh-CN。key 规范 `域.语义`。
 * 专名（YOLO/ONNX/…）不进入字典，直接写在文案里。
 */

import zhCN from './zh-CN'

export type LocaleMessages = typeof zhCN

// 当前随包提供的语言词条表；缺省语言为简体中文。
const catalogs: Record<string, LocaleMessages> = {
  'zh-CN': zhCN
}

// 当前界面语言标识，找不到目标词条时回退到 zh-CN。
let current: string = 'zh-CN'

export function setLocale(locale: string): void {
  current = catalogs[locale] ? locale : 'zh-CN'
}

export function getLocale(): string {
  return current
}

export function t(key: keyof LocaleMessages | string, vars?: Record<string, string | number>): string {
  const catalog = catalogs[current] ?? zhCN
  let text = (catalog as Record<string, string>)[key] ?? (zhCN as Record<string, string>)[key] ?? String(key)
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  return text
}
