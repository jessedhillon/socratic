import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { getObjective, type ObjectiveResponse } from '../api';
import { getLoginUrl } from '../auth';

const statusColors: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  published: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-600',
};

const extensionPolicyLabels: Record<string, string> = {
  disallowed: 'Stay within scope',
  allowed: 'May explore beyond scope',
  conditional: 'Extend if learner demonstrates mastery',
};

/**
 * Document-style view page for a single objective.
 */
const ObjectiveViewPage: React.FC = () => {
  const { objectiveId } = useParams<{ objectiveId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [objective, setObjective] = useState<ObjectiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (objectiveId) {
      fetchObjective(objectiveId);
    }
  }, [objectiveId]);

  const fetchObjective = async (id: string) => {
    try {
      const { data, response } = await getObjective({
        path: { objective_id: id },
      });
      if (!response.ok) {
        if (response.status === 401) {
          navigate(getLoginUrl(location.pathname));
          return;
        }
        if (response.status === 404) {
          setError('Objective not found');
          return;
        }
        throw new Error('Failed to fetch objective');
      }
      setObjective(data ?? null);
    } catch (err) {
      console.error('Failed to fetch objective:', err);
      setError('Failed to load objective');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Loading objective...</div>
      </div>
    );
  }

  if (error || !objective) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error || 'Objective not found'}</p>
          <button
            onClick={() => navigate('/objectives')}
            className="text-blue-600 hover:text-blue-800"
          >
            Back to Objectives
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Back navigation */}
      <button
        onClick={() => navigate('/objectives')}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-6"
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
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Back to Objectives
      </button>

      {/* Document header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 mb-6">
        <div className="flex justify-between items-start mb-4">
          <h1 className="text-3xl font-bold text-gray-900">
            {objective.title}
          </h1>
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              statusColors[objective.status] || 'bg-gray-100'
            }`}
          >
            {objective.status}
          </span>
        </div>

        <p className="text-lg text-gray-700 leading-relaxed">
          {objective.description}
        </p>

        {/* Metadata */}
        <div className="flex flex-wrap gap-6 mt-6 pt-6 border-t border-gray-200 text-sm text-gray-500">
          {objective.time_expectation_minutes && (
            <div className="flex items-center gap-2">
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
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>
                <strong>Expected Duration:</strong>{' '}
                {objective.time_expectation_minutes} minutes
              </span>
            </div>
          )}
          <div className="flex items-center gap-2">
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
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <span>
              <strong>Created:</strong>{' '}
              {new Date(objective.create_time).toLocaleDateString()}
            </span>
          </div>
          {objective.update_time && (
            <div className="flex items-center gap-2">
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
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              <span>
                <strong>Updated:</strong>{' '}
                {new Date(objective.update_time).toLocaleDateString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Scope Boundaries */}
      {objective.scope_boundaries && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-3">
            Scope Boundaries
          </h2>
          <p className="text-gray-700 leading-relaxed">
            {objective.scope_boundaries}
          </p>
        </section>
      )}

      {/* Extension Policy */}
      <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-3">
          Extension Policy
        </h2>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              objective.extension_policy === 'disallowed'
                ? 'bg-red-100 text-red-800'
                : objective.extension_policy === 'allowed'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-yellow-100 text-yellow-800'
            }`}
          >
            {objective.extension_policy}
          </span>
          <span className="text-gray-600">
            {extensionPolicyLabels[objective.extension_policy]}
          </span>
        </div>
      </section>

      {/* Initial Prompts */}
      {objective.initial_prompts && objective.initial_prompts.length > 0 && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-3">
            Initial Prompts
          </h2>
          <p className="text-gray-500 text-sm mb-4">
            Questions to start the assessment conversation
          </p>
          <ul className="space-y-3">
            {objective.initial_prompts.map((prompt, index) => (
              <li
                key={index}
                className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </span>
                <span className="text-gray-700">{prompt}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Challenge Prompts */}
      {objective.challenge_prompts &&
        objective.challenge_prompts.length > 0 && (
          <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-3">
              Challenge Prompts
            </h2>
            <p className="text-gray-500 text-sm mb-4">
              Follow-up questions to probe deeper understanding
            </p>
            <ul className="space-y-3">
              {objective.challenge_prompts.map((prompt, index) => (
                <li
                  key={index}
                  className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                >
                  <span className="flex-shrink-0 w-6 h-6 bg-orange-100 text-orange-700 rounded-full flex items-center justify-center text-sm font-medium">
                    {index + 1}
                  </span>
                  <span className="text-gray-700">{prompt}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

      {/* Rubric Criteria */}
      {objective.rubric_criteria && objective.rubric_criteria.length > 0 && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-3">
            Rubric Criteria
          </h2>
          <p className="text-gray-500 text-sm mb-4">
            Criteria used to evaluate learner understanding
          </p>
          <div className="space-y-6">
            {objective.rubric_criteria.map((criterion) => (
              <div
                key={criterion.criterion_id}
                className="border border-gray-200 rounded-lg p-4"
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-lg font-medium text-gray-800">
                    {criterion.name}
                  </h3>
                  <span className="text-sm text-gray-500">
                    Weight: {criterion.weight}
                  </span>
                </div>
                <p className="text-gray-600 mb-4">{criterion.description}</p>

                {/* Evidence Indicators */}
                {criterion.evidence_indicators &&
                  criterion.evidence_indicators.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Evidence Indicators
                      </h4>
                      <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                        {criterion.evidence_indicators.map(
                          (indicator, index) => (
                            <li key={index}>{indicator}</li>
                          )
                        )}
                      </ul>
                    </div>
                  )}

                {/* Failure Modes */}
                {criterion.failure_modes &&
                  criterion.failure_modes.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Failure Modes
                      </h4>
                      <div className="space-y-2">
                        {criterion.failure_modes.map((mode, index) => (
                          <div
                            key={index}
                            className="bg-red-50 border border-red-100 rounded p-3"
                          >
                            <span className="font-medium text-red-800">
                              {mode.name}:
                            </span>{' '}
                            <span className="text-red-700">
                              {mode.description}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Grade Thresholds */}
                {criterion.grade_thresholds &&
                  criterion.grade_thresholds.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Grade Thresholds
                      </h4>
                      <div className="grid grid-cols-2 gap-2">
                        {criterion.grade_thresholds.map((threshold, index) => (
                          <div
                            key={index}
                            className="bg-gray-50 border border-gray-200 rounded p-2 text-sm"
                          >
                            <span className="font-medium">
                              {threshold.grade}:
                            </span>{' '}
                            {threshold.description}
                            {threshold.min_evidence_count && (
                              <span className="text-gray-500">
                                {' '}
                                (min {threshold.min_evidence_count} evidence)
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default ObjectiveViewPage;
