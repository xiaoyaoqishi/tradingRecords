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

export const newsApi = {
  sync: () => api.post('/news/sync'),
  list: () => api.get('/news/issues'),
  get: (id) => api.get(`/news/issues/${id}`),
  remove: (id) => api.delete(`/news/issues/${id}`),
  translate: (id) => api.post(`/news/issues/${id}/translate`),
  progress: (id) => api.get(`/news/issues/${id}/progress`),
  today: (params = {}) => api.get('/news/today', { params }),
  articleContent: (url) => api.get('/news/article-content', { params: { url } }),
};

export default api;
