import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listMyAttempts } from '../api';
import type { AttemptHistoryItem, LearnerAttemptsListResponse } from '../api';

/**
 * Format a duration between two timestamps.
 */
function formatDuration(
  startedAt: string | null,
  completedAt: string | null
): string {
  if (!startedAt || !completedAt) return '-';

  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const durationMs = end - start;

  const minutes = Math.floor(durationMs / 60000);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  return `${minutes}m`;
}

/**
 * Format a date for display.
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/**
 * Get status badge styling based on attempt status.
 */
function getStatusBadge(status: string): { className: string; label: string } {
  switch (status) {
    case 'reviewed':
      return {
        className: 'bg-green-100 text-green-700',
        label: 'Reviewed',
      };
    case 'evaluated':
      return {
        className: 'bg-yellow-100 text-yellow-700',
        label: 'Pending Review',
      };
    case 'completed':
      return {
        className: 'bg-blue-100 text-blue-700',
        label: 'Completed',
      };
    case 'in_progress':
      return {
        className: 'bg-purple-100 text-purple-700',
        label: 'In Progress',
      };
    default:
      return {
        className: 'bg-gray-100 text-gray-700',
        label: status.replace('_', ' '),
      };
  }
}

/**
 * Attempt detail panel component.
 */
const AttemptDetail: React.FC<{
  attempt: AttemptHistoryItem;
  onClose: () => void;
}> = ({ attempt, onClose }) => {
  const statusBadge = getStatusBadge(attempt.status);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-bold text-gray-800">
              {attempt.objective_title}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
              aria-label="Close"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {attempt.objective_description && (
            <p className="text-gray-600 mb-4">
              {attempt.objective_description}
            </p>
          )}

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <span className="text-sm text-gray-500">Status</span>
              <div className="mt-1">
                <span
                  className={`px-2 py-1 rounded-full text-xs ${statusBadge.className}`}
                >
                  {statusBadge.label}
                </span>
              </div>
            </div>
            <div>
              <span className="text-sm text-gray-500">Grade</span>
              <div className="mt-1 font-semibold">{attempt.grade ?? '-'}</div>
            </div>
            <div>
              <span className="text-sm text-gray-500">Started</span>
              <div className="mt-1">
                {attempt.started_at ? formatDate(attempt.started_at) : '-'}
              </div>
            </div>
            <div>
              <span className="text-sm text-gray-500">Duration</span>
              <div className="mt-1">
                {formatDuration(
                  attempt.started_at ?? null,
                  attempt.completed_at ?? null
                )}
              </div>
            </div>
          </div>

          {/* Feedback section */}
          {attempt.status === 'reviewed' && attempt.feedback ? (
            <div className="border-t pt-4">
              <h3 className="font-semibold text-gray-800 mb-3">
                Instructor Feedback
              </h3>

              {attempt.feedback.strengths &&
                attempt.feedback.strengths.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-sm font-medium text-green-700 mb-2">
                      Strengths
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {attempt.feedback.strengths.map((strength, i) => (
                        <li key={i} className="text-gray-600">
                          {strength}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {attempt.feedback.gaps && attempt.feedback.gaps.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-orange-700 mb-2">
                    Areas for Improvement
                  </h4>
                  <ul className="list-disc list-inside space-y-1">
                    {attempt.feedback.gaps.map((gap, i) => (
                      <li key={i} className="text-gray-600">
                        {gap}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {attempt.feedback.reasoning_summary && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">
                    Summary
                  </h4>
                  <p className="text-gray-600">
                    {attempt.feedback.reasoning_summary}
                  </p>
                </div>
              )}
            </div>
          ) : attempt.status === 'evaluated' ? (
            <div className="border-t pt-4">
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                <p className="text-yellow-700">Awaiting instructor review</p>
              </div>
            </div>
          ) : null}
        </div>

        <div className="border-t px-6 py-4 bg-gray-50 rounded-b-lg">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Learner attempt history page.
 */
const HistoryPage: React.FC = () => {
  const [data, setData] = useState<LearnerAttemptsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAttempt, setSelectedAttempt] =
    useState<AttemptHistoryItem | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchAttempts();
  }, []);

  const fetchAttempts = async () => {
    try {
      const { data: attemptsData, response } = await listMyAttempts();
      if (!response.ok) {
        if (response.status === 401) {
          navigate('/');
          return;
        }
        setError('Failed to load attempt history');
        return;
      }
      setData(attemptsData ?? null);
    } catch (err) {
      console.error('Failed to fetch attempts:', err);
      setError('Failed to load attempt history');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading...</div>
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
          Assessment History
        </h1>

        {/* Attempt list */}
        <div className="space-y-4">
          {data?.attempts.map((attempt) => {
            const statusBadge = getStatusBadge(attempt.status);
            return (
              <div
                key={attempt.attempt_id}
                className="bg-white rounded-lg p-6 shadow hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setSelectedAttempt(attempt)}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">
                      {attempt.objective_title}
                    </h3>
                    <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
                      <span>{formatDate(attempt.create_time)}</span>
                      <span>
                        Duration:{' '}
                        {formatDuration(
                          attempt.started_at ?? null,
                          attempt.completed_at ?? null
                        )}
                      </span>
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${statusBadge.className}`}
                      >
                        {statusBadge.label}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    {attempt.grade && (
                      <div className="text-2xl font-bold text-gray-700">
                        {attempt.grade}
                      </div>
                    )}
                    {attempt.status === 'reviewed' && attempt.feedback && (
                      <div className="text-sm text-green-600 mt-1">
                        Feedback available
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {data?.attempts.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No attempts yet. Start an assignment from the dashboard!
            </div>
          )}
        </div>
      </div>

      {/* Detail modal */}
      {selectedAttempt && (
        <AttemptDetail
          attempt={selectedAttempt}
          onClose={() => setSelectedAttempt(null)}
        />
      )}
    </div>
  );
};

export default HistoryPage;
