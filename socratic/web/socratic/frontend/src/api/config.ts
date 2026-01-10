/**
 * API client configuration with auth interceptor.
 */
import { client } from './client.gen';

/**
 * Get the stored auth token.
 */
export function getAuthToken(): string | null {
  return localStorage.getItem('access_token');
}

/**
 * Check if user is authenticated.
 */
export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}

/**
 * Clear the auth token (logout).
 */
export function clearAuthToken(): void {
  localStorage.removeItem('access_token');
}

/**
 * Store the last login context (org slug and role) for redirects.
 */
export function setLoginContext(orgSlug: string, role: string): void {
  localStorage.setItem('login_org', orgSlug);
  localStorage.setItem('login_role', role);
}

/**
 * Get the login URL with optional redirect parameter.
 */
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
client.interceptors.request.use((request) => {
  const token = getAuthToken();
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`);
  }
  return request;
});

// Re-export the configured client
export { client };
