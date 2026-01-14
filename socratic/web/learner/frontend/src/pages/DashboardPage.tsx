import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLearnerDashboard } from '../api';
import type { LearnerDashboardResponse } from '../api';
import { useAuth } from '../contexts/AuthContext';

/**
 * Learner dashboard page showing available assignments.
 */
const DashboardPage: React.FC = () => {
  const [data, setData] = useState<LearnerDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { logout } = useAuth();

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const { data: dashboardData, response } = await getLearnerDashboard();
      if (!response.ok) {
        if (response.status === 401) {
          // Auth handled by AuthContext - just logout
          logout();
          return;
        }
        setError('Failed to load dashboard');
        return;
      }
      setData(dashboardData ?? null);
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
      setError('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  const startAssessment = (assignmentId: string) => {
    navigate(`/assessment/${assignmentId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading assignments...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">
          My Assignments
        </h1>

        {/* Summary stats */}
        {data && (
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-3xl font-bold text-green-600">
                {data.total_completed}
              </div>
              <div className="text-sm text-gray-500">Completed</div>
            </div>
            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-3xl font-bold text-blue-600">
                {data.total_in_progress}
              </div>
              <div className="text-sm text-gray-500">In Progress</div>
            </div>
            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-3xl font-bold text-gray-600">
                {data.total_pending}
              </div>
              <div className="text-sm text-gray-500">Pending</div>
            </div>
          </div>
        )}

        {/* Assignment list */}
        <div className="space-y-4">
          {data?.assignments.map((assignment) => (
            <div
              key={assignment.assignment_id}
              className="bg-white rounded-lg p-6 shadow hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">
                    {assignment.objective_title}
                  </h3>
                  <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
                    <span>
                      Attempts: {assignment.attempts_used} /{' '}
                      {assignment.attempts_used + assignment.attempts_remaining}
                    </span>
                    <span
                      className={`px-2 py-1 rounded-full text-xs ${
                        assignment.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : assignment.status === 'in_progress'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {assignment.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => startAssessment(assignment.assignment_id)}
                  disabled={!assignment.is_available || assignment.is_locked}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  {assignment.is_locked
                    ? 'Locked'
                    : !assignment.is_available
                      ? 'Not Available'
                      : assignment.attempts_used > 0
                        ? 'Continue'
                        : 'Start'}
                </button>
              </div>
            </div>
          ))}

          {data?.assignments.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No assignments available at this time.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
