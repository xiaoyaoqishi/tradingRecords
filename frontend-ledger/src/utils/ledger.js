import {
  ACCOUNT_TYPE_OPTIONS,
  DIRECTION_OPTIONS,
  TRANSACTION_TYPE_OPTIONS,
} from './enums'

const optionLabel = (options, value) => options.find((x) => x.value === value)?.label || value || '-'

export const transactionTypeLabel = (value) => optionLabel(TRANSACTION_TYPE_OPTIONS, value)

export const directionLabel = (value) => optionLabel(DIRECTION_OPTIONS, value)

export const accountTypeLabel = (value) => optionLabel(ACCOUNT_TYPE_OPTIONS, value)

export const inferDirectionByTransactionType = (txType) => {
  if (txType === 'transfer') return 'neutral'
  if (txType === 'refund') return 'income'
  if (txType === 'income' || txType === 'interest') return 'income'
  if (txType === 'expense' || txType === 'fee' || txType === 'repayment') return 'expense'
  return undefined
}
