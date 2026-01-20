import React from 'react';
import { useParams, Link } from 'react-router-dom';

/**
 * Attempt detail page - shows attempt info and feedback if reviewed.
 * Placeholder for now - will be implemented in attempt history milestone.
 */
const AttemptDetailPage: React.FC = () => {
  const { attemptId } = useParams<{ attemptId: string }>();

  return (
    <div className="py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-6">
          <Link
            to="/history"
            className="text-blue-600 hover:text-blue-800 text-sm"
          >
            &larr; Back to History
          </Link>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 mb-6">
          Attempt Details
        </h1>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 mb-4">
            Attempt ID: <code className="text-sm">{attemptId}</code>
          </p>
          <p className="text-gray-500">
            Attempt details and feedback will be displayed here once reviewed by
            instructor.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AttemptDetailPage;
