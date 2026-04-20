import apiClient from './client'

export const trackPageView = (payload) =>
  apiClient.post('/audit/track', payload, { meta: { silentError: true } })
