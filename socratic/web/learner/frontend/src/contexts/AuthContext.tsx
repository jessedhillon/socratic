import React, { createContext, useContext, useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getCurrentUser } from '../api';
import type { UserResponse } from '../api';
import { getAuthToken, clearAuthToken, getLoginUrl } from '../auth';

interface AuthContextType {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: React.ReactNode;
  requireRole?: 'learner' | 'educator';
}

export function AuthProvider({
  children,
  requireRole,
}: AuthProviderProps): React.ReactElement {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const fetchUser = async () => {
    const token = getAuthToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const { data, response } = await getCurrentUser();
      if (!response.ok) {
        if (response.status === 401) {
          clearAuthToken();
          setUser(null);
        }
        return;
      }
      setUser(data ?? null);
    } catch (err) {
      console.error('Failed to fetch user:', err);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  // Redirect if not authenticated or wrong role
  useEffect(() => {
    if (isLoading) return;

    if (!user) {
      // Not authenticated - redirect to login
      navigate(getLoginUrl(location.pathname));
      return;
    }

    if (requireRole && user.role !== requireRole) {
      // Wrong role - show error or redirect
      console.warn(
        `Access denied: required role '${requireRole}', user has '${user.role}'`
      );
      // For learner app, if user is not a learner, they shouldn't be here
      if (requireRole === 'learner' && user.role === 'educator') {
        // Redirect educators to instructor app, preserving org context
        const orgSlug = localStorage.getItem('login_org') || 'default';
        window.location.href = `http://127.0.0.1:9099/static/${orgSlug}/instructor`;
      }
    }
  }, [user, isLoading, requireRole, navigate, location.pathname]);

  const logout = () => {
    clearAuthToken();
    setUser(null);
    navigate(getLoginUrl());
  };

  const refreshUser = async () => {
    setIsLoading(true);
    await fetchUser();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
