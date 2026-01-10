import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { login, getOrganizationBySlug } from '../api';
import type { OrganizationPublicResponse } from '../api';
import { setLoginContext } from '../auth';

const VALID_ROLES = ['instructor', 'learner'] as const;
type UserRole = (typeof VALID_ROLES)[number];

/**
 * Login page for instructor and learner authentication.
 * Accessed via /{org-slug}/instructor or /{org-slug}/learner
 */
const LoginPage: React.FC = () => {
  const { orgSlug, role: roleParam } = useParams<{
    orgSlug: string;
    role: string;
  }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get('redirect');
  const [organization, setOrganization] =
    useState<OrganizationPublicResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Validate role parameter
  const isValidRole = (r: string | undefined): r is UserRole =>
    r !== undefined && VALID_ROLES.includes(r as UserRole);

  const role: UserRole | undefined = isValidRole(roleParam)
    ? roleParam
    : undefined;

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    fetchOrganization();
  }, [orgSlug]);

  const fetchOrganization = async () => {
    if (!orgSlug) {
      setError('Organization not specified');
      setLoading(false);
      return;
    }

    try {
      const { data, response } = await getOrganizationBySlug({
        path: { slug: orgSlug },
      });
      if (!response.ok) {
        if (response.status === 404) {
          setError('Organization not found');
        } else {
          setError('Failed to load organization');
        }
        return;
      }
      setOrganization(data ?? null);
    } catch (err) {
      console.error('Failed to fetch organization:', err);
      setError('Failed to load organization');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setLoginError(null);

    try {
      const {
        data,
        response,
        error: apiError,
      } = await login({
        body: { email, password },
      });

      if (!response.ok || !data) {
        const errorDetail =
          apiError && 'detail' in apiError
            ? String(apiError.detail)
            : 'Invalid credentials';
        setLoginError(errorDetail);
        return;
      }

      // Store token and login context
      localStorage.setItem('access_token', data.token.access_token);
      if (orgSlug && role) {
        setLoginContext(orgSlug, role);
      }

      // Redirect to original destination or default based on role
      if (redirectTo) {
        navigate(redirectTo);
      } else if (data.user.role === 'educator') {
        navigate('/reviews');
      } else {
        navigate('/');
      }
    } catch (err) {
      console.error('Login failed:', err);
      setLoginError('Login failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // If role is invalid, show error (this catches routes like /reviews/123 that might match)
  if (!role) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <p className="text-red-500 mb-4">Page not found</p>
          <a href="/" className="text-blue-600 hover:underline">
            Return to home
          </a>
        </div>
      </div>
    );
  }

  const roleDisplay = role === 'instructor' ? 'Instructor' : 'Learner';

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <a href="/" className="text-blue-600 hover:underline">
            Return to home
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="max-w-md w-full mx-4">
        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-gray-800">
              {organization?.name}
            </h1>
            <p className="text-gray-500 mt-2">{roleDisplay} Login</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {loginError && (
              <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
                {loginError}
              </div>
            )}

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Email
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter your password"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {submitting ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
