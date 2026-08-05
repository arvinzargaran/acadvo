import axios from 'axios';

// The API rejects any state-changing request without this header. A cross-site
// HTML form cannot set custom headers, and a cross-origin script that tries is
// forced into a CORS preflight the API's origin allowlist refuses — so its mere
// presence proves the request came from this app. See csrf_protection in
// backend/app/main.py.
export const CSRF_HEADER = 'X-Requested-With';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
  headers: { [CSRF_HEADER]: 'XMLHttpRequest' },
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
};

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    const isAuthEndpoint = originalRequest.url?.includes('/auth/');
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => client(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Bare axios, not `client` — going through the instance would re-enter
        // this interceptor on failure. The CSRF header has to be set by hand
        // for the same reason.
        await axios.post(
          `${client.defaults.baseURL}/auth/refresh`,
          {},
          { withCredentials: true, headers: { [CSRF_HEADER]: 'XMLHttpRequest' } }
        );
        processQueue(null);
        return client(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        const publicPaths = ['/', '/login', '/register'];
        if (!publicPaths.includes(window.location.pathname)) {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default client;
