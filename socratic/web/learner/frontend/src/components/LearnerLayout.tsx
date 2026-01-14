import React from 'react';
import { Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from '../contexts/AuthContext';

function LearnerHeader(): React.ReactElement {
  const { user, logout } = useAuth();

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <h1 className="text-xl font-semibold text-gray-800">Socratic</h1>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <>
                <span className="text-sm text-gray-600">{user.name}</span>
                <button
                  onClick={logout}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Sign out
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

function LearnerLayoutContent(): React.ReactElement {
  const { isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <LearnerHeader />
      <main>
        <Outlet />
      </main>
    </div>
  );
}

export default function LearnerLayout(): React.ReactElement {
  return (
    <AuthProvider requireRole="learner">
      <LearnerLayoutContent />
    </AuthProvider>
  );
}
