import axios from 'axios';
import { getAccessToken } from './supabase';

export const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');

export const api = axios.create({ baseURL: BACKEND_URL });

// Attach the Supabase session token so the API can scope resumes to this user.
api.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Signed Supabase URLs are absolute; local-mode URLs are backend-relative. */
export const absUrl = (u) => (!u ? null : /^https?:\/\//i.test(u) ? u : `${BACKEND_URL}${u}`);

export const errorMessage = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
  if (err?.code === 'ECONNABORTED') return 'The request timed out. The backend may be waking up - try again in a minute.';
  if (err?.message === 'Network Error') return 'Could not reach the backend. It may be starting up - try again shortly.';
  return err?.message || fallback;
};
