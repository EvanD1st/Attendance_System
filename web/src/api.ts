import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';

const configured = import.meta.env.VITE_API_URL || '/api/v1';
export const API_BASE_URL = configured.replace(/\/$/, '');
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});
// Kiosks authenticate independently; never refresh or attach a portal session.
export const kioskApi = axios.create({ baseURL: API_BASE_URL, timeout: 15000 });

interface RetryRequest extends InternalAxiosRequestConfig {
  _retry?: boolean;
}
let refreshPromise: Promise<string> | null = null;

export function clearTokens() {
  localStorage.removeItem('attendance_access');
  localStorage.removeItem('attendance_refresh');
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('attendance_access');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryRequest | undefined;
    const refresh = localStorage.getItem('attendance_refresh');
    if (
      error.response?.status !== 401 ||
      !request ||
      request._retry ||
      !refresh ||
      request.url?.includes('/auth/refresh/') ||
      request.url?.includes('/auth/login/') ||
      request.url?.includes('/auth/logout/')
    ) {
      throw error;
    }
    request._retry = true;
    try {
      refreshPromise ??= axios
        .post(`${API_BASE_URL}/auth/refresh/`, { refresh }, { timeout: 15000 })
        .then(({ data }) => {
          localStorage.setItem('attendance_access', data.access);
          localStorage.setItem('attendance_refresh', data.refresh);
          return data.access as string;
        })
        .finally(() => {
          refreshPromise = null;
        });
      request.headers.Authorization = `Bearer ${await refreshPromise}`;
      return api(request);
    } catch (refreshError) {
      clearTokens();
      if (window.location.pathname !== '/login') window.location.assign('/login');
      throw refreshError;
    }
  },
);

export function errorMessage(error: unknown, fallback = 'Something went wrong.') {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (typeof data?.detail === 'string') return data.detail;
    const first = data ? Object.values(data)[0] : null;
    if (Array.isArray(first)) return first[0]?.toString() || fallback;
    if (typeof first === 'string') return first;
  }
  return error instanceof Error ? error.message : fallback;
}

export async function downloadAttendance(params: URLSearchParams) {
  const response = await api.get(`/management/attendance/export.csv/?${params}`, {
    responseType: 'blob',
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'attendance.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}
