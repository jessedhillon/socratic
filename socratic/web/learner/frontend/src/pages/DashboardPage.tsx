import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listMyAssignments } from '../api';
import type {
  LearnerAssignmentSummary,
  LearnerAssignmentsListResponse,
} from '../api';
import { useAuth } from '../contexts/AuthContext';

type AssignmentDisplayStatus =
  | 'available'
  | 'locked'
  | 'completed'
  | 'not_yet_available'
  | 'expired';

interface StatusInfo {
  status: AssignmentDisplayStatus;
  label: string;
  badgeClass: string;
  dateHint?: string;
}

/**
 * Calculate detailed assignment status for display.
 */
const getAssignmentStatus = (
  assignment: LearnerAssignmentSummary
): StatusInfo => {
  const now = new Date();
  const availableFrom = assignment.available_from
    ? new Date(assignment.available_from)
    : null;
  const availableUntil = assignment.available_until
    ? new Date(assignment.available_until)
    : null;

  // Completed takes precedence
  if (assignment.status === 'completed') {
    return {
      status: 'completed',
      label: 'Completed',
      badgeClass: 'bg-blue-100 text-blue-700',
    };
  }

  // Check if expired (past available_until)
  if (availableUntil && now > availableUntil) {
    return {
      status: 'expired',
      label: 'Expired',
      badgeClass: 'bg-red-100 text-red-700',
      dateHint: `Ended ${formatDate(assignment.available_until)}`,
    };
  }

  // Check if not yet available (before available_from)
  if (availableFrom && now < availableFrom) {
    return {
      status: 'not_yet_available',
      label: 'Not Yet Available',
      badgeClass: 'bg-gray-200 text-gray-600',
      dateHint: `Starts ${formatDate(assignment.available_from)}`,
    };
  }

  // Check if locked (prerequisites not met or retake policy)
  if (assignment.is_locked) {
    return {
      status: 'locked',
      label: 'Locked',
      badgeClass: 'bg-gray-200 text-gray-600',
      dateHint: 'Prerequisites not met',
    };
  }

  // Check if no attempts remaining
  if (assignment.attempts_remaining <= 0) {
    return {
      status: 'completed',
      label: 'Max Attempts Reached',
      badgeClass: 'bg-blue-100 text-blue-700',
    };
  }

  // Available
  return {
    status: 'available',
    label: 'Available',
    badgeClass: 'bg-green-100 text-green-700',
  };
};

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
            const statusInfo = getAssignmentStatus(assignment);
            const isClickable = statusInfo.status === 'available';

            return (
              <div
                key={assignment.assignment_id}
                onClick={
                  isClickable
                    ? () => viewAssignment(assignment.assignment_id)
                    : undefined
                }
                className={`bg-white rounded-lg p-6 shadow transition-shadow ${
                  isClickable
                    ? 'hover:shadow-md cursor-pointer'
                    : 'opacity-75 cursor-not-allowed'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-gray-800">
                        {assignment.objective_title}
                      </h3>
                      {/* Status badge */}
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${statusInfo.badgeClass}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>

                    {/* Status hint (unlock time, start date, etc.) */}
                    {statusInfo.dateHint && (
                      <p className="mt-1 text-sm text-gray-500">
                        {statusInfo.dateHint}
                      </p>
                    )}

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
                    </div>
                  </div>

                  {/* Arrow indicator - only show for clickable items */}
                  {isClickable && (
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
                  )}
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
