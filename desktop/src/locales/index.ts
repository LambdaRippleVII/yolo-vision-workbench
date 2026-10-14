/**
 * 轻量 i18n：默认 zh-CN。key 规范 `域.语义`。
 * 专名（YOLO/ONNX/…）不进入字典，直接写在文案里。
 */

import zhCN from './zh-CN'

export type LocaleMessages = typeof zhCN

const catalogs: Record<string, LocaleMessages> = {
  'zh-CN': zhCN
}

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
