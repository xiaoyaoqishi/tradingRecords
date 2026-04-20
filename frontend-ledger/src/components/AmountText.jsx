import { formatMoney, formatSignedMoney } from '../utils/money'

export default function AmountText({
  value,
  currency = 'CNY',
  direction,
  transactionType,
  signed = false,
}) {
  const isIncome = direction === 'income' || ['income', 'refund', 'interest'].includes(transactionType)
  const isExpense = direction === 'expense' || ['expense', 'fee', 'repayment'].includes(transactionType)
  const className = isIncome ? 'amount-income' : isExpense ? 'amount-expense' : 'amount-neutral'
  const text = signed
    ? `${formatSignedMoney(value, direction, transactionType)} ${currency || 'CNY'}`
    : formatMoney(value, currency)

  return <span className={className}>{text}</span>
}
