export const removeEmptyParams = (params = {}) => {
  const next = {}
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return
    if (typeof value === 'string' && value.trim() === '') return
    next[key] = value
  })
  return next
}

export const parseSearchParams = (search) => {
  const parsed = {}
  const params = new URLSearchParams(search || '')
  params.forEach((value, key) => {
    parsed[key] = value
  })
  return parsed
}

export const buildSearchParams = (params = {}) => {
  const cleaned = removeEmptyParams(params)
  const sp = new URLSearchParams()
  Object.entries(cleaned).forEach(([key, value]) => {
    sp.set(key, String(value))
  })
  return sp.toString()
}
