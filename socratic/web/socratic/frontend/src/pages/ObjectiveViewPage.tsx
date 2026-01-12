import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  getObjective,
  updateObjective,
  createObjective,
  type ObjectiveResponse,
  type ObjectiveUpdateRequest,
  type ObjectiveCreateRequest,
  type ExtensionPolicy,
  type ObjectiveStatus,
} from '../api';
import { getLoginUrl } from '../auth';
import EditableText, {
  type EditableTextHandle,
} from '../components/EditableText';
import EditableSelect from '../components/EditableSelect';

const statusColors: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  published: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-600',
};

const extensionPolicyOptions = [
  {
    value: 'allowed',
    label: 'Yes, students may explore beyond the scope',
  },
  {
    value: 'conditional',
    label: 'Only once they demonstrate mastery within the scope',
  },
  {
    value: 'disallowed',
    label: 'No, students must remain within this scope',
  },
];

const statusOptions = [
  { value: 'draft', label: 'Draft' },
  { value: 'published', label: 'Published' },
  { value: 'archived', label: 'Archived' },
];

// Default values for a new objective
const defaultObjective: ObjectiveResponse = {
  objective_id: '',
  title: '',
  description: '',
  status: 'draft' as ObjectiveStatus,
  extension_policy: 'disallowed' as ExtensionPolicy,
  scope_boundaries: '',
  time_expectation_minutes: null,
  initial_prompts: [],
  challenge_prompts: [],
  rubric_criteria: [],
  create_time: new Date().toISOString(),
  update_time: new Date().toISOString(),
};

/**
 * Document-style view page for a single objective.
 * Also handles creating new objectives when objectiveId is "new".
 */
const ObjectiveViewPage: React.FC = () => {
  const { objectiveId } = useParams<{ objectiveId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const isNew = objectiveId === 'new';
  const [objective, setObjective] = useState<ObjectiveResponse | null>(
    isNew ? { ...defaultObjective } : null
  );
  const [loading, setLoading] = useState(!isNew);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const initialPromptRefs = useRef<Map<number, EditableTextHandle>>(new Map());
  const challengePromptRefs = useRef<Map<number, EditableTextHandle>>(
    new Map()
  );

  const saveField = useCallback(
    async (updates: ObjectiveUpdateRequest) => {
      if (isSaving) return;

      // For new objectives, we need to create first
      if (isNew) {
        // Merge updates with current objective state
        const currentState = objective || defaultObjective;
        const merged = { ...currentState, ...updates };

        setIsSaving(true);
        try {
          const createRequest: ObjectiveCreateRequest = {
            title: merged.title || '',
            description: merged.description || '',
            scope_boundaries: merged.scope_boundaries || undefined,
            time_expectation_minutes:
              merged.time_expectation_minutes || undefined,
            initial_prompts: merged.initial_prompts || undefined,
            challenge_prompts: merged.challenge_prompts || undefined,
            extension_policy: merged.extension_policy,
          };
          const { data, response } = await createObjective({
            body: createRequest,
          });
          if (!response.ok) {
            console.error('Failed to create:', response.status);
            return;
          }
          if (data) {
            // Navigate to the new objective's page
            navigate(`/objectives/${data.objective_id}`, { replace: true });
          }
        } catch (err) {
          console.error('Failed to create objective:', err);
        } finally {
          setIsSaving(false);
        }
        return;
      }

      // For existing objectives, update as before
      if (!objectiveId) return;
      setIsSaving(true);
      try {
        const { data, response } = await updateObjective({
          path: { objective_id: objectiveId },
          body: updates,
        });
        if (!response.ok) {
          console.error('Failed to save:', response.status);
          return;
        }
        if (data) {
          setObjective(data);
        }
      } catch (err) {
        console.error('Failed to save field:', err);
      } finally {
        setIsSaving(false);
      }
    },
    [objectiveId, isSaving, isNew, objective, navigate]
  );

  const handleAddInitialPrompt = useCallback(() => {
    if (!objective) return;
    const prompts = objective.initial_prompts || [];
    // Find first empty prompt
    const emptyIndex = prompts.findIndex((p) => p.trim() === '');
    if (emptyIndex >= 0) {
      // Focus the empty prompt
      initialPromptRefs.current.get(emptyIndex)?.focus();
    } else {
      // Add new prompt and focus it after render
      const newPrompts = [...prompts, ''];
      setObjective({ ...objective, initial_prompts: newPrompts });
      setTimeout(() => {
        initialPromptRefs.current.get(newPrompts.length - 1)?.focus();
      }, 0);
    }
  }, [objective]);

  const handleAddChallengePrompt = useCallback(() => {
    if (!objective) return;
    const prompts = objective.challenge_prompts || [];
    // Find first empty prompt
    const emptyIndex = prompts.findIndex((p) => p.trim() === '');
    if (emptyIndex >= 0) {
      // Focus the empty prompt
      challengePromptRefs.current.get(emptyIndex)?.focus();
    } else {
      // Add new prompt and focus it after render
      const newPrompts = [...prompts, ''];
      setObjective({ ...objective, challenge_prompts: newPrompts });
      setTimeout(() => {
        challengePromptRefs.current.get(newPrompts.length - 1)?.focus();
      }, 0);
    }
  }, [objective]);

  useEffect(() => {
    if (objectiveId && !isNew) {
      fetchObjective(objectiveId);
    }
  }, [objectiveId, isNew]);

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
        className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-6 cursor-pointer"
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
          <EditableText
            value={objective.title}
            onChange={(value) => setObjective({ ...objective, title: value })}
            onSave={() => saveField({ title: objective.title })}
            placeholder="Click to edit title..."
            className="flex-1 mr-4"
            textClassName="text-3xl font-bold text-gray-900"
          />
          <EditableSelect
            value={objective.status}
            options={statusOptions}
            onChange={(value) => {
              setObjective({ ...objective, status: value as ObjectiveStatus });
              saveField({ status: value as ObjectiveStatus });
            }}
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              statusColors[objective.status] || 'bg-gray-100'
            }`}
          />
        </div>

        <EditableText
          value={objective.description}
          onChange={(value) =>
            setObjective({ ...objective, description: value })
          }
          onSave={() => saveField({ description: objective.description })}
          placeholder="Click to edit description..."
          multiline
          rows={4}
          textClassName="text-lg text-gray-700 leading-relaxed"
        />

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
      <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-3">
          Scope Boundaries
        </h2>
        <EditableText
          value={objective.scope_boundaries || ''}
          onChange={(value) =>
            setObjective({ ...objective, scope_boundaries: value })
          }
          onSave={() =>
            saveField({ scope_boundaries: objective.scope_boundaries })
          }
          placeholder="Define the boundaries of this objective..."
          multiline
          rows={3}
          textClassName="text-gray-700 leading-relaxed"
        />

        {/* Scope Extension */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            Scope extension
          </h3>
          <p className="text-gray-600 mb-4">
            Are students allowed to explore and discuss elements of the topic
            which are outside of these boundaries?
          </p>
          <div className="space-y-1">
            {extensionPolicyOptions.map((option) => (
              <label
                key={option.value}
                className={`flex items-center gap-3 px-3 py-2 -mx-3 rounded-lg cursor-pointer transition-colors duration-150 ${
                  objective.extension_policy === option.value
                    ? 'bg-blue-50'
                    : 'hover:bg-gray-900/[0.04]'
                }`}
              >
                <span
                  className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors duration-150 ${
                    objective.extension_policy === option.value
                      ? 'border-blue-600'
                      : 'border-gray-400'
                  }`}
                >
                  {objective.extension_policy === option.value && (
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-600" />
                  )}
                </span>
                <input
                  type="radio"
                  name="extension_policy"
                  value={option.value}
                  checked={objective.extension_policy === option.value}
                  onChange={(e) => {
                    const value = e.target.value as ExtensionPolicy;
                    setObjective({ ...objective, extension_policy: value });
                    saveField({ extension_policy: value });
                  }}
                  className="sr-only"
                />
                <span className="text-gray-700">{option.label}</span>
              </label>
            ))}
          </div>
        </div>
      </section>

      {/* Initial Prompts */}
      <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-3">
          Initial Prompts
        </h2>
        <p className="text-gray-500 text-sm mb-4">
          Questions to start the assessment conversation
        </p>
        <ul className="space-y-3">
          {(objective.initial_prompts || []).map((prompt, index) => (
            <li
              key={index}
              className="group flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
                {index + 1}
              </span>
              <EditableText
                ref={(el) => {
                  if (el) {
                    initialPromptRefs.current.set(index, el);
                  } else {
                    initialPromptRefs.current.delete(index);
                  }
                }}
                value={prompt}
                onChange={(value) => {
                  const newPrompts = [...(objective.initial_prompts || [])];
                  newPrompts[index] = value;
                  setObjective({ ...objective, initial_prompts: newPrompts });
                }}
                onSave={() => {
                  saveField({ initial_prompts: objective.initial_prompts });
                }}
                className="flex-1"
                textClassName="text-gray-700"
              />
              <button
                onClick={() => {
                  const newPrompts = [...(objective.initial_prompts || [])];
                  newPrompts.splice(index, 1);
                  setObjective({ ...objective, initial_prompts: newPrompts });
                  saveField({ initial_prompts: newPrompts });
                }}
                className="flex-shrink-0 p-1 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 hover:bg-gray-200 transition-all duration-150 text-gray-500 hover:text-red-600"
                title="Delete prompt"
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
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </li>
          ))}
        </ul>
        <button
          onClick={handleAddInitialPrompt}
          className="mt-3 text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          Add prompt
        </button>
      </section>

      {/* Challenge Prompts */}
      <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-3">
          Challenge Prompts
        </h2>
        <p className="text-gray-500 text-sm mb-4">
          Follow-up questions to probe deeper understanding
        </p>
        <ul className="space-y-3">
          {(objective.challenge_prompts || []).map((prompt, index) => (
            <li
              key={index}
              className="group flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <span className="flex-shrink-0 w-6 h-6 bg-orange-100 text-orange-700 rounded-full flex items-center justify-center text-sm font-medium">
                {index + 1}
              </span>
              <EditableText
                ref={(el) => {
                  if (el) {
                    challengePromptRefs.current.set(index, el);
                  } else {
                    challengePromptRefs.current.delete(index);
                  }
                }}
                value={prompt}
                onChange={(value) => {
                  const newPrompts = [...(objective.challenge_prompts || [])];
                  newPrompts[index] = value;
                  setObjective({ ...objective, challenge_prompts: newPrompts });
                }}
                onSave={() => {
                  saveField({ challenge_prompts: objective.challenge_prompts });
                }}
                className="flex-1"
                textClassName="text-gray-700"
              />
              <button
                onClick={() => {
                  const newPrompts = [...(objective.challenge_prompts || [])];
                  newPrompts.splice(index, 1);
                  setObjective({ ...objective, challenge_prompts: newPrompts });
                  saveField({ challenge_prompts: newPrompts });
                }}
                className="flex-shrink-0 p-1 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 hover:bg-gray-200 transition-all duration-150 text-gray-500 hover:text-red-600"
                title="Delete prompt"
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
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </li>
          ))}
        </ul>
        <button
          onClick={handleAddChallengePrompt}
          className="mt-3 text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          Add prompt
        </button>
      </section>

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
