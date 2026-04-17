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

export const authApi = {
  check: () => api.get('/auth/check'),
  logout: () => api.post('/auth/logout'),
};

export const monitorApi = {
  realtime: () => api.get('/monitor/realtime'),
  history: () => api.get('/monitor/history'),
  listSites: () => api.get('/monitor/sites'),
  createSite: (data) => api.post('/monitor/sites', data),
  updateSite: (id, data) => api.put(`/monitor/sites/${id}`, data),
  deleteSite: (id) => api.delete(`/monitor/sites/${id}`),
  siteResults: (id, params) => api.get(`/monitor/sites/${id}/results`, { params }),
};

export const userAdminApi = {
  list: () => api.get('/admin/users'),
  create: (data) => api.post('/admin/users', data),
  update: (id, data) => api.put(`/admin/users/${id}`, data),
  remove: (id) => api.delete(`/admin/users/${id}`),
  toggleActive: (id) => api.post(`/admin/users/${id}/toggle-active`),
  resetPassword: (id, data) => api.post(`/admin/users/${id}/reset-password`, data),
};

export const auditApi = {
  track: (data) => api.post('/audit/track', data),
  list: (params) => api.get('/audit/logs', { params }),
  remove: (id) => api.delete(`/audit/logs/${id}`),
};

export default api;
