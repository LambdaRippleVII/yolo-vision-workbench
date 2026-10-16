/** 定义首次安装 Python 依赖时可用的包索引地址。 */
// 首次初始化时依次尝试的国内 PyPI 简易索引。
export const BUILTIN_PACKAGE_SOURCES = [
  {
    id: 'tsinghua',
    label: '清华镜像',
    indexUrl: 'https://pypi.tuna.tsinghua.edu.cn/simple'
  },
  {
    id: 'aliyun',
    label: '阿里云镜像',
    indexUrl: 'https://mirrors.aliyun.com/pypi/simple'
  },
  {
    id: 'ustc',
    label: '中科大镜像',
    indexUrl: 'https://pypi.mirrors.ustc.edu.cn/simple'
  }
] as const

export type BuiltinPackageSourceId = (typeof BUILTIN_PACKAGE_SOURCES)[number]['id']
export type PackageSourceId = BuiltinPackageSourceId | 'custom'

export interface PackageSourceSelection {
  id: PackageSourceId
  customUrl: string
}

export interface PackageSourceEndpoint {
  id: PackageSourceId
  label: string
  indexUrl: string
}

// 新安装默认从清华镜像开始，安装器会在失败时继续尝试另外两个国内源。
export const DEFAULT_PACKAGE_SOURCE: PackageSourceSelection = {
  id: 'tsinghua',
  customUrl: ''
}

/** 验证并规整用户选中的包源配置。 */
export function normalizePackageSource(value: unknown): PackageSourceSelection {
  if (!value || typeof value !== 'object') {
    throw new Error('包镜像源配置格式不正确。')
  }

  const candidate = value as { id?: unknown; customUrl?: unknown }
  const id = candidate.id
  const customUrl = typeof candidate.customUrl === 'string' ? candidate.customUrl.trim() : ''
  const isBuiltin = BUILTIN_PACKAGE_SOURCES.some((source) => source.id === id)

  if (id === 'custom') {
    let parsed: URL
    try {
      parsed = new URL(customUrl)
    } catch {
      throw new Error('自定义镜像源需要填写完整的 http 或 https 地址。')
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error('自定义镜像源只支持 http 或 https 地址。')
    }
    if (!parsed.hostname) {
      throw new Error('自定义镜像源地址缺少主机名。')
    }
    return { id, customUrl: parsed.toString().replace(/\/+$/, '') }
  }

  if (!isBuiltin) throw new Error('请选择有效的 Python 包镜像源。')
  return { id: id as BuiltinPackageSourceId, customUrl }
}

/** 按首选源优先级返回安装镜像，并去除重复地址。 */
export function getPackageSourceAttempts(selection: PackageSourceSelection): PackageSourceEndpoint[] {
  const normalized = normalizePackageSource(selection)
  const preferred = normalized.id === 'custom'
    ? { id: 'custom' as const, label: '自定义镜像', indexUrl: normalized.customUrl }
    : BUILTIN_PACKAGE_SOURCES.find((source) => source.id === normalized.id)!
  const candidates: PackageSourceEndpoint[] = [
    preferred,
    ...BUILTIN_PACKAGE_SOURCES.filter((source) => source.id !== normalized.id)
  ]
  const seen = new Set<string>()
  return candidates.filter((source) => {
    const key = source.indexUrl.replace(/\/+$/, '').toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
