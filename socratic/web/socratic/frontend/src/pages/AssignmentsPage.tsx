import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  listAssignments,
  listObjectives,
  listLearners,
  createAssignment,
  createBulkAssignments,
  type AssignmentResponse,
  type ObjectiveResponse,
  type LearnerResponse,
  type RetakePolicy,
} from '../api';
import { getLoginUrl } from '../auth';

const retakePolicyLabels: Record<string, string> = {
  none: 'No retakes',
  immediate: 'Immediate',
  delayed: 'After delay',
  manual_approval: 'Requires approval',
};

const retakePolicyOptions: { value: RetakePolicy; label: string }[] = [
  { value: 'none', label: 'No retakes allowed' },
  { value: 'immediate', label: 'Immediate retake allowed' },
  { value: 'delayed', label: 'Retake after delay' },
  { value: 'manual_approval', label: 'Retake requires approval' },
];

/**
 * Assignments management page for instructors.
 */
const AssignmentsPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [assignments, setAssignments] = useState<AssignmentResponse[]>([]);
  const [objectives, setObjectives] = useState<Map<string, ObjectiveResponse>>(
    new Map()
  );
  const [learners, setLearners] = useState<Map<string, LearnerResponse>>(
    new Map()
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedObjective, setSelectedObjective] = useState<string>('');
  const [selectedLearners, setSelectedLearners] = useState<string[]>([]);
  const [availableFrom, setAvailableFrom] = useState<string>('');
  const [availableUntil, setAvailableUntil] = useState<string>('');
  const [maxAttempts, setMaxAttempts] = useState<number>(1);
  const [retakePolicy, setRetakePolicy] = useState<RetakePolicy>('none');
  const [retakeDelayHours, setRetakeDelayHours] = useState<number>(24);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      // Fetch all data in parallel
      const [assignmentsResult, objectivesResult, learnersResult] =
        await Promise.all([
          listAssignments(),
          listObjectives(),
          listLearners(),
        ]);

      // Check for auth errors
      if (
        assignmentsResult.response.status === 401 ||
        objectivesResult.response.status === 401 ||
        learnersResult.response.status === 401
      ) {
        navigate(getLoginUrl(location.pathname));
        return;
      }

      if (!assignmentsResult.response.ok) {
        throw new Error('Failed to fetch assignments');
      }

      // Build lookup maps
      const objectivesMap = new Map<string, ObjectiveResponse>();
      for (const obj of objectivesResult.data?.objectives ?? []) {
        objectivesMap.set(obj.objective_id, obj);
      }

      const learnersMap = new Map<string, LearnerResponse>();
      for (const learner of learnersResult.data?.learners ?? []) {
        learnersMap.set(learner.user_id, learner);
      }

      setAssignments(assignmentsResult.data?.assignments ?? []);
      setObjectives(objectivesMap);
      setLearners(learnersMap);
    } catch (err) {
      console.error('Failed to fetch data:', err);
      setError('Failed to load assignments');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setSelectedObjective('');
    setSelectedLearners([]);
    setAvailableFrom('');
    setAvailableUntil('');
    setMaxAttempts(1);
    setRetakePolicy('none');
    setRetakeDelayHours(24);
    setFormError(null);
  };

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedObjective || selectedLearners.length === 0) {
      setFormError('Please select an objective and at least one learner');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);

    try {
      const assignmentData = {
        objective_id: selectedObjective,
        available_from: availableFrom
          ? new Date(availableFrom).toISOString()
          : null,
        available_until: availableUntil
          ? new Date(availableUntil).toISOString()
          : null,
        max_attempts: maxAttempts,
        retake_policy: retakePolicy,
        retake_delay_hours:
          retakePolicy === 'delayed' ? retakeDelayHours : null,
      };

      if (selectedLearners.length === 1) {
        // Single assignment
        const { response } = await createAssignment({
          body: {
            ...assignmentData,
            assigned_to: selectedLearners[0],
          },
        });
        if (!response.ok) {
          throw new Error('Failed to create assignment');
        }
      } else {
        // Bulk assignment
        const { response } = await createBulkAssignments({
          body: {
            ...assignmentData,
            assigned_to: selectedLearners,
          },
        });
        if (!response.ok) {
          throw new Error('Failed to create assignments');
        }
      }

      // Refresh data and close form
      await fetchData();
      setShowForm(false);
      resetForm();
    } catch (err) {
      console.error('Failed to create assignment:', err);
      setFormError('Failed to create assignment. Please try again.');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleLearnerToggle = (learnerId: string) => {
    setSelectedLearners((prev) =>
      prev.includes(learnerId)
        ? prev.filter((id) => id !== learnerId)
        : [...prev, learnerId]
    );
  };

  const handleSelectAllLearners = () => {
    const allLearnerIds = Array.from(learners.keys());
    if (selectedLearners.length === allLearnerIds.length) {
      setSelectedLearners([]);
    } else {
      setSelectedLearners(allLearnerIds);
    }
  };

  const formatDate = (dateStr: string | null | undefined): string => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Loading assignments...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
        </div>
      </div>
    );
  }

  const publishedObjectives = Array.from(objectives.values()).filter(
    (o) => o.status === 'published'
  );
  const hasPublishedObjectives = publishedObjectives.length > 0;
  const hasLearners = learners.size > 0;
  const canCreateAssignment = hasPublishedObjectives && hasLearners;

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Assignments</h1>
        <button
          onClick={() => {
            resetForm();
            setShowForm(!showForm);
          }}
          disabled={!canCreateAssignment}
          className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${
            canCreateAssignment
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
          title={
            !hasPublishedObjectives
              ? 'Publish an objective first'
              : !hasLearners
                ? 'Invite learners first'
                : undefined
          }
        >
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          Create Assignment
        </button>
      </div>

      {/* Create Assignment Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Create Assignment
          </h2>
          <form onSubmit={handleCreateAssignment} className="space-y-4">
            {formError && (
              <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">
                {formError}
              </div>
            )}

            {/* Objective Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Objective <span className="text-red-500">*</span>
              </label>
              <select
                value={selectedObjective}
                onChange={(e) => setSelectedObjective(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="">Select an objective...</option>
                {publishedObjectives.map((obj) => (
                  <option key={obj.objective_id} value={obj.objective_id}>
                    {obj.title}
                  </option>
                ))}
              </select>
            </div>

            {/* Learner Selection */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="block text-sm font-medium text-gray-700">
                  Learners <span className="text-red-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={handleSelectAllLearners}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  {selectedLearners.length === learners.size
                    ? 'Deselect all'
                    : 'Select all'}
                </button>
              </div>
              <div className="border border-gray-300 rounded-md max-h-40 overflow-y-auto">
                {Array.from(learners.values()).map((learner) => (
                  <label
                    key={learner.user_id}
                    className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedLearners.includes(learner.user_id)}
                      onChange={() => handleLearnerToggle(learner.user_id)}
                      className="mr-3"
                    />
                    <span className="text-sm">
                      {learner.name}{' '}
                      <span className="text-gray-500">({learner.email})</span>
                    </span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {selectedLearners.length} learner(s) selected
              </p>
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Available From
                </label>
                <input
                  type="datetime-local"
                  value={availableFrom}
                  onChange={(e) => setAvailableFrom(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Available Until
                </label>
                <input
                  type="datetime-local"
                  value={availableUntil}
                  onChange={(e) => setAvailableUntil(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Max Attempts */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Attempts
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={maxAttempts}
                onChange={(e) => setMaxAttempts(parseInt(e.target.value) || 1)}
                className="w-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Retake Policy */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Retake Policy
              </label>
              <select
                value={retakePolicy}
                onChange={(e) =>
                  setRetakePolicy(e.target.value as RetakePolicy)
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {retakePolicyOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Retake Delay (conditional) */}
            {retakePolicy === 'delayed' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Retake Delay (hours)
                </label>
                <input
                  type="number"
                  min={1}
                  value={retakeDelayHours}
                  onChange={(e) =>
                    setRetakeDelayHours(parseInt(e.target.value) || 24)
                  }
                  className="w-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            )}

            {/* Form Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
                disabled={formSubmitting}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={formSubmitting}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {formSubmitting
                  ? 'Creating...'
                  : selectedLearners.length > 1
                    ? `Create ${selectedLearners.length} Assignments`
                    : 'Create Assignment'}
              </button>
            </div>
          </form>
        </div>
      )}

      {assignments.length === 0 && !showForm ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="text-gray-400 mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-medium text-gray-700 mb-2">
            No assignments yet
          </h2>
          <p className="text-gray-500 mb-6">
            {!hasPublishedObjectives
              ? 'Publish an objective first, then assign it to learners.'
              : !hasLearners
                ? 'Invite learners to your organization first.'
                : 'Create assignments to assess your learners.'}
          </p>
          {canCreateAssignment && (
            <button
              onClick={() => setShowForm(true)}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Create Your First Assignment
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4">
          {assignments.map((assignment) => {
            const objective = objectives.get(assignment.objective_id);
            const learner = learners.get(assignment.assigned_to);

            return (
              <div
                key={assignment.assignment_id}
                className="group bg-white rounded-lg shadow p-6 hover:shadow-md transition-all"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">
                      {objective?.title || (
                        <span className="text-gray-400 italic font-normal">
                          Unknown Objective
                        </span>
                      )}
                    </h3>
                    <p className="text-sm text-gray-600">
                      Assigned to:{' '}
                      <span className="font-medium">
                        {learner?.name || learner?.email || 'Unknown Learner'}
                      </span>
                    </p>
                  </div>
                  <div className="text-right text-sm text-gray-500">
                    <div>Max attempts: {assignment.max_attempts}</div>
                    <div>
                      {retakePolicyLabels[assignment.retake_policy] ||
                        assignment.retake_policy}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6 text-sm text-gray-500 mt-4">
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
                        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                    Available: {formatDate(assignment.available_from)} —{' '}
                    {formatDate(assignment.available_until)}
                  </span>
                  <span>
                    Created{' '}
                    {new Date(assignment.create_time).toLocaleDateString()}
                  </span>
                  {/* Delete button will be added in SOC-68 */}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AssignmentsPage;
