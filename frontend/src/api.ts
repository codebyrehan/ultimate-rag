import axios, { AxiosInstance, AxiosError } from 'axios';

const api: AxiosInstance = axios.create({
  baseURL: '/',
  timeout: 120000,
});

let isRefreshing = false;
let pendingRequests: Array<() => void> = [];

const flushPending = (token: string | null) => {
  pendingRequests.forEach((cb) => cb());
  pendingRequests = [];
};

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (!localStorage.getItem('refresh_token')) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('tenant_name');
        window.location.href = '/login';
        return Promise.reject(error);
      }
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push(() => {
            const token = localStorage.getItem('access_token');
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            } else {
              reject(error);
            }
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const refresh = localStorage.getItem('refresh_token');
        const resp = await axios.post('/auth/refresh', {
          refresh_token: refresh,
        });
        localStorage.setItem('access_token', resp.data.access_token);
        if (resp.data.refresh_token) {
          localStorage.setItem('refresh_token', resp.data.refresh_token);
        }
        originalRequest.headers.Authorization = `Bearer ${resp.data.access_token}`;
        flushPending(resp.data.access_token);
        return api(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('tenant_name');
        flushPending(null);
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  },
);

export default api;
