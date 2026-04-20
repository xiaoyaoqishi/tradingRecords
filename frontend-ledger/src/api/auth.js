import apiClient from './client'

export const check = () => apiClient.get('/auth/check')

export const logout = () => apiClient.post('/auth/logout')
