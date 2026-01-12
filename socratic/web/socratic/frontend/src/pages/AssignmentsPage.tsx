import React from 'react';

/**
 * Assignments management page for instructors.
 */
const AssignmentsPage: React.FC = () => {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Assignments</h1>
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
          Create objectives first, then assign them to learners.
        </p>
        <button
          className="px-6 py-2 bg-gray-300 text-gray-500 rounded-lg cursor-not-allowed"
          disabled
        >
          Create Assignment
        </button>
        <p className="text-sm text-gray-400 mt-2">
          You need at least one objective to create assignments.
        </p>
      </div>
    </div>
  );
};

export default AssignmentsPage;
