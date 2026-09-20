// 产物类型枚举：与后端 app/cqrs.py ArtifactType 保持一致
export const ARTIFACT_TYPES = [
  { value: 'model', label: '模型' },
  { value: 'dataset', label: '数据集' },
  { value: 'log', label: '日志' },
  { value: 'graph', label: '图' },
]

export const ARTIFACT_TYPE_VALUES = ARTIFACT_TYPES.map((t) => t.value)

export const ARTIFACT_TYPE_LABELS = Object.fromEntries(
  ARTIFACT_TYPES.map((t) => [t.value, t.label]),
)

// 页面侧第一道拦截：非法/未选类型给出原因
export function validateArtifactType(v) {
  if (!v) return '请选择产物类型（模型 / 数据集 / 日志 / 图）'
  if (!ARTIFACT_TYPE_VALUES.includes(v)) {
    return `产物类型非法：“${v}” 不在允许范围内，仅支持 ${ARTIFACT_TYPES.map(
      (t) => t.label,
    ).join(' / ')}`
  }
  return ''
}
