import { client } from './api/client.gen';

export function getAuthToken(): string | null {
  return localStorage.getItem('access_token');
}

export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}

export function clearAuthToken(): void {
  localStorage.removeItem('access_token');
}

export function setLoginContext(orgSlug: string, role: string): void {
  localStorage.setItem('login_org', orgSlug);
  localStorage.setItem('login_role', role);
}

export function getLoginUrl(redirectTo?: string): string {
  const orgSlug = localStorage.getItem('login_org') || 'default';
  const role = localStorage.getItem('login_role') || 'learner';
  const base = `/${orgSlug}/${role}`;
  if (redirectTo) {
    return `${base}?redirect=${encodeURIComponent(redirectTo)}`;
  }
  return base;
}

// Configure the client with auth interceptor
client.interceptors.request.use((request: Request) => {
  const token = getAuthToken();
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`);
  }
  return request;
});
