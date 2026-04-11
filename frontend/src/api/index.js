import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const redirect = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?redirect=${redirect}`;
    }
    return Promise.reject(err);
  }
);

export const tradeApi = {
  list: (params) => api.get('/trades', { params }),
  count: (params) => api.get('/trades/count', { params }),
  searchOptions: (params) => api.get('/trades/search-options', { params }),
  get: (id) => api.get(`/trades/${id}`),
  create: (data) => api.post('/trades', data),
  update: (id, data) => api.put(`/trades/${id}`, data),
  delete: (id) => api.delete(`/trades/${id}`),
  stats: (params) => api.get('/trades/statistics', { params }),
  analytics: (params) => api.get('/trades/analytics', { params }),
  importPaste: (data) => api.post('/trades/import-paste', data),
  positions: (params) => api.get('/trades/positions', { params }),
  sources: () => api.get('/trades/sources'),
};

export const brokerApi = {
  list: () => api.get('/trade-brokers'),
  create: (data) => api.post('/trade-brokers', data),
  update: (id, data) => api.put(`/trade-brokers/${id}`, data),
  delete: (id) => api.delete(`/trade-brokers/${id}`),
};

export const reviewApi = {
  list: (params) => api.get('/reviews', { params }),
  get: (id) => api.get(`/reviews/${id}`),
  create: (data) => api.post('/reviews', data),
  update: (id, data) => api.put(`/reviews/${id}`, data),
  delete: (id) => api.delete(`/reviews/${id}`),
  upsertTradeLinks: (id, data) => api.put(`/reviews/${id}/trade-links`, data),
};

export const reviewSessionApi = {
  list: (params) => api.get('/review-sessions', { params }),
  get: (id) => api.get(`/review-sessions/${id}`),
  create: (data) => api.post('/review-sessions', data),
  update: (id, data) => api.put(`/review-sessions/${id}`, data),
  delete: (id) => api.delete(`/review-sessions/${id}`),
  upsertTradeLinks: (id, data) => api.put(`/review-sessions/${id}/trade-links`, data),
  createFromSelection: (data) => api.post('/review-sessions/create-from-selection', data),
};

export const tradePlanApi = {
  list: (params) => api.get('/trade-plans', { params }),
  get: (id) => api.get(`/trade-plans/${id}`),
  create: (data) => api.post('/trade-plans', data),
  update: (id, data) => api.put(`/trade-plans/${id}`, data),
  delete: (id) => api.delete(`/trade-plans/${id}`),
  upsertTradeLinks: (id, data) => api.put(`/trade-plans/${id}/trade-links`, data),
  upsertReviewSessionLinks: (id, data) => api.put(`/trade-plans/${id}/review-session-links`, data),
  createFollowupReviewSession: (id) => api.post(`/trade-plans/${id}/create-followup-review-session`),
};

export const tradeReviewApi = {
  taxonomy: () => api.get('/trade-review-taxonomy'),
  get: (tradeId) => api.get(`/trades/${tradeId}/review`),
  upsert: (tradeId, data) => api.put(`/trades/${tradeId}/review`, data),
  delete: (tradeId) => api.delete(`/trades/${tradeId}/review`),
};

export const tradeSourceApi = {
  get: (tradeId) => api.get(`/trades/${tradeId}/source-metadata`),
  upsert: (tradeId, data) => api.put(`/trades/${tradeId}/source-metadata`, data),
};

export const knowledgeApi = {
  list: (params) => api.get('/knowledge-items', { params }),
  categories: () => api.get('/knowledge-items/categories'),
  get: (id) => api.get(`/knowledge-items/${id}`),
  create: (data) => api.post('/knowledge-items', data),
  update: (id, data) => api.put(`/knowledge-items/${id}`, data),
  delete: (id) => api.delete(`/knowledge-items/${id}`),
};

export default api;
