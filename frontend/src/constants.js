// 挂载产物类型枚举：值需与后端 app.schemas.ArtifactType 保持一致
export const ARTIFACT_TYPES = ['model', 'dataset', 'log', 'graph']

export const ARTIFACT_TYPE_LABELS = {
  model: '模型',
  dataset: '数据集',
  log: '日志',
  graph: '图',
}

export const ARTIFACT_TYPE_TAG_TYPES = {
  model: 'info',
  dataset: 'success',
  log: 'default',
  graph: 'warning',
}

export const ARTIFACT_TYPE_OPTIONS = ARTIFACT_TYPES.map((value) => ({
  label: `${ARTIFACT_TYPE_LABELS[value]}（${value}）`,
  value,
}))

export function artifactTypeLabel(value) {
  return ARTIFACT_TYPE_LABELS[value] || value || '—'
}

export function isArtifactType(value) {
  return ARTIFACT_TYPES.includes(value)
}

// 页面侧拦截：给出与服务端一致的中文原因
export function illegalArtifactTypeReason(value) {
  return `非法产物类型: ${JSON.stringify(value)}；只允许 ${ARTIFACT_TYPES.join(' / ')}（模型/数据集/日志/图）`
}
