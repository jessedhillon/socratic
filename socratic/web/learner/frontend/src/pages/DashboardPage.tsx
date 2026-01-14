import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listMyAssignments } from '../api';
import type { LearnerAssignmentsListResponse } from '../api';
import { useAuth } from '../contexts/AuthContext';

/**
 * Format duration in minutes to a human-readable string.
 */
const formatDuration = (minutes: number | null | undefined): string | null => {
  if (minutes == null) return null;
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
};

/**
 * Format a date string to a readable format.
 */
const formatDate = (dateStr: string | null | undefined): string | null => {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

/**
 * Learner assignments list page.
 */
const DashboardPage: React.FC = () => {
  const [data, setData] = useState<LearnerAssignmentsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { logout } = useAuth();

  useEffect(() => {
    fetchAssignments();
  }, []);

  const fetchAssignments = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: assignmentsData, response } = await listMyAssignments();
      if (!response.ok) {
        if (response.status === 401) {
          logout();
          return;
        }
        setError('Failed to load assignments');
        return;
      }
      setData(assignmentsData ?? null);
    } catch (err) {
      console.error('Failed to fetch assignments:', err);
      setError('Failed to load assignments');
    } finally {
      setLoading(false);
    }
  };

  const viewAssignment = (assignmentId: string) => {
    navigate(`/assignments/${assignmentId}`);
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
          <button
            onClick={fetchAssignments}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Retry
          </button>
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

        {/* Assignment list */}
        <div className="space-y-4">
          {data?.assignments.map((assignment) => {
            const duration = formatDuration(
              assignment.expected_duration_minutes
            );
            const availableFrom = formatDate(assignment.available_from);
            const availableUntil = formatDate(assignment.available_until);
            const hasAvailabilityWindow = availableFrom || availableUntil;

            return (
              <div
                key={assignment.assignment_id}
                onClick={() => viewAssignment(assignment.assignment_id)}
                className="bg-white rounded-lg p-6 shadow hover:shadow-md transition-shadow cursor-pointer"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-gray-800">
                        {assignment.objective_title}
                      </h3>
                      {/* Status badge */}
                      {assignment.is_locked ? (
                        <span className="px-2 py-1 rounded-full text-xs bg-gray-200 text-gray-600">
                          Locked
                        </span>
                      ) : assignment.status === 'completed' ? (
                        <span className="px-2 py-1 rounded-full text-xs bg-green-100 text-green-700">
                          Completed
                        </span>
                      ) : !assignment.is_available ? (
                        <span className="px-2 py-1 rounded-full text-xs bg-yellow-100 text-yellow-700">
                          Unavailable
                        </span>
                      ) : (
                        <span className="px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-700">
                          Available
                        </span>
                      )}
                    </div>

                    {/* Description preview */}
                    {assignment.objective_description && (
                      <p className="mt-2 text-sm text-gray-600 line-clamp-2">
                        {assignment.objective_description}
                      </p>
                    )}

                    {/* Meta info row */}
                    <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-gray-500">
                      {/* Expected duration */}
                      {duration && (
                        <span className="flex items-center gap-1">
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          {duration}
                        </span>
                      )}

                      {/* Attempts */}
                      <span>
                        {assignment.attempts_used} of{' '}
                        {assignment.attempts_used +
                          assignment.attempts_remaining}{' '}
                        attempts used
                      </span>

                      {/* Availability window */}
                      {hasAvailabilityWindow && (
                        <span className="text-gray-400">
                          {availableFrom && availableUntil
                            ? `${availableFrom} – ${availableUntil}`
                            : availableFrom
                              ? `From ${availableFrom}`
                              : `Until ${availableUntil}`}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Arrow indicator */}
                  <svg
                    className="w-5 h-5 text-gray-400 ml-4 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </div>
            );
          })}

          {data?.assignments.length === 0 && (
            <div className="text-center py-12">
              <div className="text-gray-400 mb-2">
                <svg
                  className="w-12 h-12 mx-auto"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>
              </div>
              <p className="text-gray-500">No assignments yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Check back later for new assignments from your instructor.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
