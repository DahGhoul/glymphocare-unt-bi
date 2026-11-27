import type { GlobalFilters } from '../types/glympho';

const TOKEN_KEY = 'glymphocare_jwt';
const USER_KEY = 'glymphocare_user';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthSession(token: string, user: unknown): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function filtersToQuery(filters?: Partial<GlobalFilters>): string {
  if (!filters) return '';
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      params.set(k, String(v));
    }
  });
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const resp = await fetch(path, { ...init, headers });
  if (resp.status === 401) {
    clearAuthSession();
    window.dispatchEvent(new Event('glympho:unauthorized'));
  }
  if (!resp.ok) {
    let msg = `Error ${resp.status}`;
    try {
      const err = await resp.json();
      msg = err.detail || msg;
    } catch {
      // keep status message
    }
    throw new Error(msg);
  }
  return resp.json() as Promise<T>;
}

export async function apiDownload(path: string, init: RequestInit, filename: string): Promise<void> {
  const token = getStoredToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const resp = await fetch(path, { ...init, headers });
  if (!resp.ok) {
    throw new Error(`No se pudo descargar (${resp.status})`);
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
