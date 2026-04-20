export default function RuleMatchSummary({ matchJson }) {
  const match = matchJson || {}
  const rows = []
  Object.entries(match).forEach(([k, v]) => {
    if (v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)) return
    rows.push(`${k}: ${Array.isArray(v) ? v.join(' / ') : v}`)
  })
  return rows.length ? rows.join('；') : '-'
}
