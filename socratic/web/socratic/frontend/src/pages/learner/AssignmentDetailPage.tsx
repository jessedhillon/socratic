import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getMyAssignment } from '../../api';
import type {
  AssignmentWithAttemptsResponse,
  SocraticWebSocraticViewAssignmentAttemptResponse as AttemptResponse,
  RetakePolicy,
  Grade,
} from '../../api';
import { useAuth } from '../../contexts/AuthContext';

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
 * Get human-readable retake policy description.
 */
const getRetakePolicyDescription = (
  policy: RetakePolicy,
  delayHours: number | null | undefined
): string => {
  switch (policy) {
    case 'immediate':
      return 'You can retake immediately after completing an attempt';
    case 'delayed':
      return delayHours
        ? `You must wait ${delayHours} hours between attempts`
        : 'There is a waiting period between attempts';
    case 'manual_approval':
      return 'Instructor approval is required for retakes';
    case 'none':
      return 'Only one attempt is allowed';
    default:
      return '';
  }
};

/**
 * Get grade badge styling.
 */
const getGradeBadge = (
  grade: Grade | null | undefined
): { label: string; className: string } => {
  switch (grade) {
    case 'S':
      return {
        label: 'Superb',
        className: 'bg-green-100 text-green-700',
      };
    case 'A':
      return { label: 'Advanced', className: 'bg-blue-100 text-blue-700' };
    case 'C':
      return {
        label: 'Developing',
        className: 'bg-yellow-100 text-yellow-700',
      };
    case 'F':
      return { label: 'Beginning', className: 'bg-red-100 text-red-700' };
    default:
      return { label: 'Pending', className: 'bg-gray-100 text-gray-600' };
  }
};

/**
 * Get status badge styling.
 */
const getStatusBadge = (
  status: string
): { label: string; className: string } => {
  switch (status) {
    case 'completed':
    case 'evaluated':
    case 'reviewed':
      return { label: 'Completed', className: 'bg-blue-100 text-blue-700' };
    case 'in_progress':
      return {
        label: 'In Progress',
        className: 'bg-yellow-100 text-yellow-700',
      };
    case 'not_started':
    default:
      return { label: 'Not Started', className: 'bg-gray-100 text-gray-600' };
  }
};

/**
 * Assignment detail page - shows full assignment info, attempt history, and start button.
 */
const AssignmentDetailPage: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const { logout } = useAuth();

  const [assignment, setAssignment] =
    useState<AssignmentWithAttemptsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!assignmentId) return;
    fetchAssignment();
  }, [assignmentId]);

  const fetchAssignment = async () => {
    if (!assignmentId) return;

    setLoading(true);
    setError(null);

    try {
      const { data, response } = await getMyAssignment({
        path: { assignment_id: assignmentId },
      });

      if (!response.ok) {
        if (response.status === 401) {
          logout();
          return;
        }
        if (response.status === 404) {
          setError('Assignment not found');
          return;
        }
        setError('Failed to load assignment');
        return;
      }

      setAssignment(data ?? null);
    } catch (err) {
      console.error('Failed to fetch assignment:', err);
      setError('Failed to load assignment');
    } finally {
      setLoading(false);
    }
  };

  const handleStartAssessment = () => {
    if (assignmentId) {
      navigate(`/assessments/${assignmentId}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading assignment...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="mb-6">
            <Link
              to="/assignments"
              className="text-blue-600 hover:text-blue-800 text-sm"
            >
              &larr; Back to Assignments
            </Link>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <p className="text-red-500 mb-4">{error}</p>
            <button
              onClick={fetchAssignment}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!assignment) {
    return null;
  }

  const duration = formatDuration(assignment.expected_duration_minutes);
  const attempts = assignment.attempts ?? [];
  const sortedAttempts = [...attempts].sort(
    (a, b) =>
      new Date(b.create_time).getTime() - new Date(a.create_time).getTime()
  );
  const canStart = assignment.is_available && !assignment.is_locked;

  return (
    <div className="py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Back link */}
        <div className="mb-6">
          <Link
            to="/assignments"
            className="text-blue-600 hover:text-blue-800 text-sm inline-flex items-center gap-1"
          >
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
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Assignments
          </Link>
        </div>

        {/* Main content card */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {/* Header section */}
          <div className="p-6 border-b border-gray-200">
            <h1 className="text-2xl font-bold text-gray-800 mb-2">
              {assignment.objective_title ?? 'Assignment'}
            </h1>
            {assignment.objective_description && (
              <p className="text-gray-600">
                {assignment.objective_description}
              </p>
            )}
          </div>

          {/* Info section */}
          <div className="p-6 border-b border-gray-200 bg-gray-50">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Duration */}
              <div>
                <div className="text-sm text-gray-500 mb-1">
                  Expected Duration
                </div>
                <div className="flex items-center gap-2">
                  <svg
                    className="w-5 h-5 text-gray-400"
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
                  <span
                    className={
                      duration ? 'font-medium' : 'font-medium text-gray-400'
                    }
                  >
                    {duration ?? 'No time limit'}
                  </span>
                </div>
              </div>

              {/* Attempts */}
              <div>
                <div className="text-sm text-gray-500 mb-1">Attempts</div>
                <div className="font-medium">
                  {attempts.length} of {assignment.max_attempts} used
                </div>
                {(assignment.attempts_remaining ?? 0) > 0 && (
                  <div className="text-sm text-gray-500">
                    {assignment.attempts_remaining} remaining
                  </div>
                )}
              </div>

              {/* Availability */}
              <div>
                <div className="text-sm text-gray-500 mb-1">Availability</div>
                {assignment.available_from && (
                  <div>
                    <div className="font-medium">
                      {formatDate(assignment.available_from)}
                    </div>
                    <div className="text-sm text-gray-500">start</div>
                  </div>
                )}
                {assignment.available_until && (
                  <div>
                    <div className="font-medium">
                      {formatDate(assignment.available_until)}
                    </div>
                    <div className="text-sm text-gray-500">end</div>
                  </div>
                )}
                {!assignment.available_from && !assignment.available_until && (
                  <div className="font-medium text-green-600">
                    Always available
                  </div>
                )}
              </div>

              {/* Retake Policy */}
              <div>
                <div className="text-sm text-gray-500 mb-1">Retake Policy</div>
                <div className="font-medium">
                  {getRetakePolicyDescription(
                    assignment.retake_policy,
                    assignment.retake_delay_hours
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Status indicators */}
          {(assignment.is_locked || !assignment.is_available) && (
            <div className="p-4 bg-yellow-50 border-b border-gray-200">
              {assignment.is_locked && (
                <div className="flex items-center gap-2 text-yellow-700">
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                    />
                  </svg>
                  <span>
                    This assignment is locked. Complete prerequisite assignments
                    first.
                  </span>
                </div>
              )}
              {!assignment.is_locked && !assignment.is_available && (
                <div className="flex items-center gap-2 text-yellow-700">
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <span>
                    {(assignment.attempts_remaining ?? 0) <= 0
                      ? 'No attempts remaining.'
                      : 'This assignment is not currently available.'}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Action section */}
          <div className="p-6">
            <button
              onClick={handleStartAssessment}
              disabled={!canStart}
              className={`w-full md:w-auto px-6 py-3 rounded-lg font-medium text-lg transition-colors ${
                canStart
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              {attempts.length === 0 ? 'Start Assessment' : 'Start New Attempt'}
            </button>
          </div>

          {/* Attempt history */}
          {sortedAttempts.length > 0 && (
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">
                Attempt History
              </h2>
              <div className="space-y-3">
                {sortedAttempts.map((attempt, index) => (
                  <AttemptCard
                    key={attempt.attempt_id}
                    attempt={attempt}
                    attemptNumber={sortedAttempts.length - index}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Individual attempt card component.
 */
const AttemptCard: React.FC<{
  attempt: AttemptResponse;
  attemptNumber: number;
}> = ({ attempt, attemptNumber }) => {
  const statusBadge = getStatusBadge(attempt.status);
  const gradeBadge = attempt.grade ? getGradeBadge(attempt.grade) : null;

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="font-medium text-gray-700">
            Attempt #{attemptNumber}
          </span>
          <span
            className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge.className}`}
          >
            {statusBadge.label}
          </span>
          {gradeBadge && (
            <span
              className={`px-2 py-1 rounded-full text-xs font-medium ${gradeBadge.className}`}
            >
              {gradeBadge.label}
            </span>
          )}
        </div>
        <div className="text-sm text-gray-500">
          {attempt.started_at && (
            <span>Started: {formatDate(attempt.started_at)}</span>
          )}
          {attempt.completed_at && (
            <span className="ml-4">
              Completed: {formatDate(attempt.completed_at)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default AssignmentDetailPage;
