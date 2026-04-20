const normalizeAmount = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num)) return 0
  return num
}

export const formatMoney = (value, currency = 'CNY') => {
  const amount = normalizeAmount(value)
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: currency || 'CNY',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

export const formatSignedMoney = (value, direction, transactionType) => {
  const amount = Math.abs(normalizeAmount(value))
  const isIncome = direction === 'income' || ['income', 'refund', 'interest'].includes(transactionType)
  const isExpense = direction === 'expense' || ['expense', 'fee', 'repayment'].includes(transactionType)
  if (isIncome) return `+${amount.toFixed(2)}`
  if (isExpense) return `-${amount.toFixed(2)}`
  return amount.toFixed(2)
}
