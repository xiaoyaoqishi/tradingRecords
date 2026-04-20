import apiClient from './client'

export const listAccounts = () => apiClient.get('/ledger/accounts')
export const createAccount = (payload) => apiClient.post('/ledger/accounts', payload)
export const updateAccount = (id, payload) => apiClient.put(`/ledger/accounts/${id}`, payload)
export const deleteAccount = (id) => apiClient.delete(`/ledger/accounts/${id}`)

export const listCategories = (params) => apiClient.get('/ledger/categories', { params })
export const createCategory = (payload) => apiClient.post('/ledger/categories', payload)
export const updateCategory = (id, payload) => apiClient.put(`/ledger/categories/${id}`, payload)
export const deleteCategory = (id) => apiClient.delete(`/ledger/categories/${id}`)

export const listTransactions = (params) => apiClient.get('/ledger/transactions', { params })
export const getTransaction = (id) => apiClient.get(`/ledger/transactions/${id}`)
export const createTransaction = (payload, options = {}) =>
  apiClient.post('/ledger/transactions', payload, { params: { apply_rules: options.applyRules !== false } })
export const updateTransaction = (id, payload, options = {}) =>
  apiClient.put(`/ledger/transactions/${id}`, payload, { params: { apply_rules: options.applyRules !== false } })
export const deleteTransaction = (id) => apiClient.delete(`/ledger/transactions/${id}`)

export const getDashboard = (params) => apiClient.get('/ledger/dashboard', { params })

export const previewImport = (formData) =>
  apiClient.post('/ledger/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

export const commitImport = (payload) => apiClient.post('/ledger/import/commit', payload)

export const listImportTemplates = () => apiClient.get('/ledger/import/templates')
export const createImportTemplate = (payload) => apiClient.post('/ledger/import/templates', payload)
export const deleteImportTemplate = (id) => apiClient.delete(`/ledger/import/templates/${id}`)

export const listRules = () => apiClient.get('/ledger/rules')
export const createRule = (payload) => apiClient.post('/ledger/rules', payload)
export const updateRule = (id, payload) => apiClient.put(`/ledger/rules/${id}`, payload)
export const deleteRule = (id) => apiClient.delete(`/ledger/rules/${id}`)
export const previewRules = (payload) => apiClient.post('/ledger/rules/preview', payload)
export const reapplyRules = (payload) => apiClient.post('/ledger/rules/reapply', payload)
