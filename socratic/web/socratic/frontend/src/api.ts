/**
 * API utilities for authenticated requests.
 */

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

/**
 * Make an authenticated fetch request.
 * Automatically includes the Authorization header if a token exists.
 */
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(options.headers);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(url, {
    ...options,
    headers,
  });
}
