import React, { useState } from 'react';
import type { ExtensionPolicy, ObjectiveCreateRequest } from '../api';

interface ObjectiveFormProps {
  onSubmit: (data: ObjectiveCreateRequest) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
}

/**
 * Form for creating or editing a learning objective.
 */
const ObjectiveForm: React.FC<ObjectiveFormProps> = ({
  onSubmit,
  onCancel,
  isSubmitting = false,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scopeBoundaries, setScopeBoundaries] = useState('');
  const [timeExpectation, setTimeExpectation] = useState('');
  const [extensionPolicy, setExtensionPolicy] =
    useState<ExtensionPolicy>('disallowed');
  const [initialPrompts, setInitialPrompts] = useState('');
  const [challengePrompts, setChallengePrompts] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    if (!description.trim()) {
      setError('Description is required');
      return;
    }

    const data: ObjectiveCreateRequest = {
      title: title.trim(),
      description: description.trim(),
      scope_boundaries: scopeBoundaries.trim() || null,
      time_expectation_minutes: timeExpectation
        ? parseInt(timeExpectation, 10)
        : null,
      extension_policy: extensionPolicy,
      initial_prompts: initialPrompts
        .split('\n')
        .map((p) => p.trim())
        .filter((p) => p.length > 0),
      challenge_prompts: challengePrompts
        .split('\n')
        .map((p) => p.trim())
        .filter((p) => p.length > 0),
    };

    try {
      await onSubmit(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save objective');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Title */}
      <div>
        <label
          htmlFor="title"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Title <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="e.g., Understanding Photosynthesis"
          disabled={isSubmitting}
        />
      </div>

      {/* Description */}
      <div>
        <label
          htmlFor="description"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Description <span className="text-red-500">*</span>
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="Describe what mastery of this objective looks like..."
          disabled={isSubmitting}
        />
      </div>

      {/* Scope Boundaries */}
      <div>
        <label
          htmlFor="scope"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Scope Boundaries
        </label>
        <textarea
          id="scope"
          value={scopeBoundaries}
          onChange={(e) => setScopeBoundaries(e.target.value)}
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="What is explicitly out of scope for this assessment..."
          disabled={isSubmitting}
        />
        <p className="mt-1 text-sm text-gray-500">
          Define what topics are outside the scope of this assessment.
        </p>
      </div>

      {/* Time Expectation */}
      <div>
        <label
          htmlFor="time"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Expected Duration (minutes)
        </label>
        <input
          type="number"
          id="time"
          value={timeExpectation}
          onChange={(e) => setTimeExpectation(e.target.value)}
          min="1"
          max="120"
          className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="15"
          disabled={isSubmitting}
        />
      </div>

      {/* Extension Policy */}
      <div>
        <label
          htmlFor="extension"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Extension Policy
        </label>
        <select
          id="extension"
          value={extensionPolicy}
          onChange={(e) =>
            setExtensionPolicy(e.target.value as ExtensionPolicy)
          }
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={isSubmitting}
        >
          <option value="disallowed">Disallowed - Stay within scope</option>
          <option value="allowed">Allowed - May explore beyond scope</option>
          <option value="conditional">
            Conditional - Extend if learner demonstrates mastery
          </option>
        </select>
        <p className="mt-1 text-sm text-gray-500">
          Whether the AI can explore topics beyond the defined scope.
        </p>
      </div>

      {/* Initial Prompts */}
      <div>
        <label
          htmlFor="initialPrompts"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Initial Prompts
        </label>
        <textarea
          id="initialPrompts"
          value={initialPrompts}
          onChange={(e) => setInitialPrompts(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="Enter opening questions, one per line..."
          disabled={isSubmitting}
        />
        <p className="mt-1 text-sm text-gray-500">
          Questions to start the conversation. One per line.
        </p>
      </div>

      {/* Challenge Prompts */}
      <div>
        <label
          htmlFor="challengePrompts"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Challenge Prompts
        </label>
        <textarea
          id="challengePrompts"
          value={challengePrompts}
          onChange={(e) => setChallengePrompts(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="Enter follow-up questions to probe deeper, one per line..."
          disabled={isSubmitting}
        />
        <p className="mt-1 text-sm text-gray-500">
          Follow-up questions to probe deeper understanding. One per line.
        </p>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {isSubmitting ? 'Creating...' : 'Create Objective'}
        </button>
      </div>
    </form>
  );
};

export default ObjectiveForm;
