import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  listObjectives,
  createObjective,
  type ObjectiveResponse,
  type ObjectiveCreateRequest,
} from '../api';
import { getLoginUrl } from '../auth';
import ObjectiveForm from '../components/ObjectiveForm';

const statusColors: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  published: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-600',
};

/**
 * Objectives management page for instructors.
 */
const ObjectivesPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [objectives, setObjectives] = useState<ObjectiveResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchObjectives();
  }, []);

  const fetchObjectives = async () => {
    try {
      const { data, response } = await listObjectives();
      if (!response.ok) {
        if (response.status === 401) {
          navigate(getLoginUrl(location.pathname));
          return;
        }
        throw new Error('Failed to fetch objectives');
      }
      setObjectives(data?.objectives ?? []);
    } catch (err) {
      console.error('Failed to fetch objectives:', err);
      setError('Failed to load objectives');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateObjective = async (data: ObjectiveCreateRequest) => {
    setIsSubmitting(true);
    try {
      const { response } = await createObjective({ body: data });
      if (!response.ok) {
        throw new Error('Failed to create objective');
      }
      await fetchObjectives();
      setShowCreateModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Loading objectives...</div>
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

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          Learning Objectives
        </h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
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
          Create Objective
        </button>
      </div>

      {objectives.length === 0 ? (
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
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
          </div>
          <h2 className="text-xl font-medium text-gray-700 mb-2">
            No objectives yet
          </h2>
          <p className="text-gray-500 mb-6">
            Create learning objectives to assess your learners.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Create Your First Objective
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {objectives.map((objective) => (
            <div
              key={objective.objective_id}
              onClick={() => navigate(`/objectives/${objective.objective_id}`)}
              className="bg-white rounded-lg shadow p-6 hover:bg-gray-900/[0.08] hover:shadow-md transition-all cursor-pointer"
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-lg font-semibold text-gray-800">
                  {objective.title}
                </h3>
                <span
                  className={`px-2 py-1 rounded-full text-xs font-medium ${
                    statusColors[objective.status] || 'bg-gray-100'
                  }`}
                >
                  {objective.status}
                </span>
              </div>
              <p className="text-gray-600 mb-4 line-clamp-2">
                {objective.description}
              </p>
              <div className="flex items-center gap-4 text-sm text-gray-500">
                {objective.time_expectation_minutes && (
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
                    {objective.time_expectation_minutes} min
                  </span>
                )}
                {objective.initial_prompts &&
                  objective.initial_prompts.length > 0 && (
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
                          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                        />
                      </svg>
                      {objective.initial_prompts.length} prompts
                    </span>
                  )}
                <span>
                  Created {new Date(objective.create_time).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold text-gray-800">
                  Create Learning Objective
                </h2>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                  disabled={isSubmitting}
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
            </div>
            <div className="p-6">
              <ObjectiveForm
                onSubmit={handleCreateObjective}
                onCancel={() => setShowCreateModal(false)}
                isSubmitting={isSubmitting}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ObjectivesPage;
