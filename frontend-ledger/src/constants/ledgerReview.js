export const REVIEW_STATUSES = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  APPROVED: 'approved',
  ACCEPTED: 'accepted',
  IGNORED: 'ignored',
  REJECTED: 'rejected',
  DUPLICATE: 'duplicate',
  INVALID: 'invalid',
  COMMITTED: 'committed',
}

export const COMMIT_ELIGIBLE_REVIEW_STATUSES = new Set([
  REVIEW_STATUSES.CONFIRMED,
  REVIEW_STATUSES.APPROVED,
  REVIEW_STATUSES.ACCEPTED,
])

export const REVIEW_STATUS_META = {
  [REVIEW_STATUSES.PENDING]: { label: '待确认', color: 'blue' },
  [REVIEW_STATUSES.CONFIRMED]: { label: '已确认', color: 'green' },
  [REVIEW_STATUSES.APPROVED]: { label: '已批准', color: 'green' },
  [REVIEW_STATUSES.ACCEPTED]: { label: '已接受', color: 'green' },
  [REVIEW_STATUSES.IGNORED]: { label: '已忽略', color: 'default' },
  [REVIEW_STATUSES.REJECTED]: { label: '已拒绝', color: 'red' },
  [REVIEW_STATUSES.DUPLICATE]: { label: '重复标记', color: 'orange' },
  [REVIEW_STATUSES.INVALID]: { label: '无效', color: 'red' },
  [REVIEW_STATUSES.COMMITTED]: { label: '已入账', color: 'cyan' },
}

export const COMMITTED_BATCH_STATUS = REVIEW_STATUSES.COMMITTED
export const COMMITTED_BATCH_READONLY_MESSAGE = '该批次已入账，如需重新处理，请先删除批次并确认回滚已入账交易。'

export function isCommittedBatch(batch) {
  return batch?.status === COMMITTED_BATCH_STATUS
}
