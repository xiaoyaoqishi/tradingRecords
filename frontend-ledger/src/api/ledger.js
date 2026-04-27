import apiClient from './client'

export const createImportBatch = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post('/ledger/import-batches', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const listImportBatches = () => apiClient.get('/ledger/import-batches')
export const listCategories = () => apiClient.get('/ledger/categories')
export const getImportBatch = (id) => apiClient.get(`/ledger/import-batches/${id}`)
export const deleteImportBatch = (id) => apiClient.delete(`/ledger/import-batches/${id}`)
export const parseImportBatch = (id) => apiClient.post(`/ledger/import-batches/${id}/parse`)
export const classifyImportBatch = (id) => apiClient.post(`/ledger/import-batches/${id}/classify`)
export const dedupeImportBatch = (id) => apiClient.post(`/ledger/import-batches/${id}/dedupe`)
export const reprocessImportBatch = (id) => apiClient.post(`/ledger/import-batches/${id}/reprocess`)
export const listImportReviewRows = (id, params = {}) => apiClient.get(`/ledger/import-batches/${id}/review-rows`, { params })
export const getImportReviewInsights = (id) => apiClient.get(`/ledger/import-batches/${id}/review-insights`)
export const commitImportBatch = (id) => apiClient.post(`/ledger/import-batches/${id}/commit`)

export const reviewBulkCategory = (id, payload) => apiClient.post(`/ledger/import-batches/${id}/review/bulk-category`, payload)
export const reviewBulkMerchant = (id, payload) => apiClient.post(`/ledger/import-batches/${id}/review/bulk-merchant`, payload)
export const reviewBulkConfirm = (id, payload) => apiClient.post(`/ledger/import-batches/${id}/review/bulk-confirm`, payload)
export const reviewReclassifyPending = (id) => apiClient.post(`/ledger/import-batches/${id}/review/reclassify-pending`)
export const reviewGenerateRule = (id, payload) => apiClient.post(`/ledger/import-batches/${id}/review/generate-rule`, payload)

export const listMerchants = () => apiClient.get('/ledger/merchants')
export const createMerchant = (payload) => apiClient.post('/ledger/merchants', payload)
export const updateMerchant = (id, payload) => apiClient.put(`/ledger/merchants/${id}`, payload)

export const listRules = () => apiClient.get('/ledger/rules')
export const createRule = (payload) => apiClient.post('/ledger/rules', payload)
export const updateRule = (id, payload) => apiClient.put(`/ledger/rules/${id}`, payload)
export const deleteRule = (id) => apiClient.delete(`/ledger/rules/${id}`)

export const getAnalyticsSummary = (params = {}) => apiClient.get('/ledger/analytics/summary', { params })
export const getAnalyticsCategoryBreakdown = (params = {}) => apiClient.get('/ledger/analytics/category-breakdown', { params })
export const getAnalyticsPlatformBreakdown = (params = {}) => apiClient.get('/ledger/analytics/platform-breakdown', { params })
export const getAnalyticsTopMerchants = (params = {}) => apiClient.get('/ledger/analytics/top-merchants', { params })
export const getAnalyticsMonthlyTrend = (params = {}) => apiClient.get('/ledger/analytics/monthly-trend', { params })
export const getAnalyticsUnrecognizedBreakdown = (params = {}) => apiClient.get('/ledger/analytics/unrecognized-breakdown', { params })
