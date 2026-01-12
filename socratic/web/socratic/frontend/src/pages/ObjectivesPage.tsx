import React from 'react';

/**
 * Objectives management page for instructors.
 * Placeholder for SOC-47.
 */
const ObjectivesPage: React.FC = () => {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">
        Learning Objectives
      </h1>
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
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          onClick={() => {
            // TODO: Implement objective creation (SOC-47)
            alert('Objective creation coming soon!');
          }}
        >
          Create Objective
        </button>
      </div>
    </div>
  );
};

export default ObjectivesPage;
