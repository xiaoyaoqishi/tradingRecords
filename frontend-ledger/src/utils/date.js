import dayjs from 'dayjs'

export const formatDate = (value) => {
  if (!value) return '-'
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD') : '-'
}

export const formatDateTime = (value) => {
  if (!value) return '-'
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : '-'
}

export const getDefaultLast30DaysRange = () => {
  const end = dayjs().endOf('day')
  const start = end.subtract(29, 'day').startOf('day')
  return [start, end]
}
