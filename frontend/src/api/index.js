import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
    }
    return Promise.reject(err);
  }
);

export const tradeApi = {
  list: (params) => api.get('/trades', { params }),
  count: (params) => api.get('/trades/count', { params }),
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

export default api;
