/** Map technical errors to user-facing Chinese messages. */

export function formatError(e: unknown): string {
  const raw = String(e ?? '')
  if (!raw) return '未知错误'
  if (raw.includes('WebSocket not connected') || raw.includes('not connected')) {
    return '与后端通信未就绪，请稍候或点击「重启后端服务」'
  }
  if (raw.includes('timeout') || raw.includes('TimeoutError')) {
    return '请求超时，请稍后重试'
  }
  if (raw.includes('BAD_REQUEST')) {
    return '请求参数不正确'
  }
  if (raw.includes('MODEL_LOAD_FAILED')) {
    return '模型加载失败，请检查权重文件与依赖'
  }
  if (raw.includes('MODEL_NOT_FOUND')) {
    return '未找到模型，请先在「模型管理」中添加'
  }
  if (raw.includes('INFERENCE_ERROR')) {
    return '推理失败，请查看日志'
  }
  if (raw.includes('MEDIA_NOT_FOUND')) {
    return '找不到媒体文件'
  }
  if (raw.includes('TASK_NOT_FOUND')) {
    return '任务不存在或已清理'
  }
  if (raw.includes('INTERNAL')) {
    return '内部错误，请查看日志'
  }
  // already Chinese or short technical
  if (/[\u4e00-\u9fff]/.test(raw)) return raw
  return raw.length > 80 ? raw.slice(0, 80) + '…' : raw
}
