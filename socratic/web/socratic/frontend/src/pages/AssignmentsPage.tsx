import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  listAssignments,
  listObjectives,
  listLearners,
  type AssignmentResponse,
  type ObjectiveResponse,
  type LearnerResponse,
} from '../api';
import { getLoginUrl } from '../auth';

const retakePolicyLabels: Record<string, string> = {
  none: 'No retakes',
  immediate: 'Immediate',
  delayed: 'After delay',
  manual_approval: 'Requires approval',
};

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

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Assignments</h1>
        {/* Create button will be added in SOC-67 */}
      </div>

      {assignments.length === 0 ? (
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
