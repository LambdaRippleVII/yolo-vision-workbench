export type LabelPos = 'top' | 'bottom' | 'left' | 'right'
export type TextRotate = 0 | 90 | 180 | 270

// 检测框、默认标签和缺省类别色共用的琥珀色。
export const DEFAULT_BOX_COLOR = '#E8890C'

export interface LabelItemStyle {
  color: string
  bg: string
  /** false 表示透明，不绘制标签背景。 */
  bgEnabled: boolean
  fontSize: number
  bold: boolean
  rotate: TextRotate
}

export interface LabelItem {
  id: string
  place: LabelPos
  template: string
  style: LabelItemStyle
}

export interface BoxStyleConfig {
  color: string
  lineWidth: number
}

export interface LabelSettings {
  mode: 'auto' | 'manual'
  autoTemplate: string
  autoStyle: LabelItemStyle
  labels: LabelItem[]
  box: BoxStyleConfig
}

export function defaultLabelStyle(): LabelItemStyle {
  return { color: '#2A1A02', bg: DEFAULT_BOX_COLOR, bgEnabled: true, fontSize: 12, bold: true, rotate: 0 }
}

export function defaultLabelSettings(): LabelSettings {
  return {
    mode: 'auto',
    autoTemplate: '{id}:{display}',
    autoStyle: defaultLabelStyle(),
    labels: [
      {
        id: 'l1',
        place: 'top',
        template: '{id}:{display}',
        style: defaultLabelStyle()
      }
    ],
    box: { color: DEFAULT_BOX_COLOR, lineWidth: 2 }
  }
}

export function fillTemplate(tpl: string, o: {
  id: number
  class_name: string
  display_name: string
  class_id: number
  confidence: number
  model_id: string
  track_id?: number | null
}): string {
  return (tpl || '')
    .replace(/\{id\}/g, String(o.id))
    .replace(/\{display\}/g, o.display_name || o.class_name)
    .replace(/\{class\}/g, o.class_name)
    .replace(/\{class_id\}/g, String(o.class_id))
    .replace(/\{confidence\}/g, `${Math.round((o.confidence || 0) * 100)}%`)
    .replace(/\{model_id\}/g, String(o.model_id || ''))
    .replace(/\{model\}/g, String(o.model_id || ''))
    .replace(/\{track_id\}/g, o.track_id != null ? String(o.track_id) : '—')
}
