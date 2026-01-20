import React from 'react';
import { useParams, Link } from 'react-router-dom';

/**
 * Assignment detail page - shows assignment info and allows starting assessment.
 * Placeholder for now - will be implemented in assignments view milestone.
 */
const AssignmentDetailPage: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();

  return (
    <div className="py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-6">
          <Link
            to="/assignments"
            className="text-blue-600 hover:text-blue-800 text-sm"
          >
            &larr; Back to Assignments
          </Link>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 mb-6">
          Assignment Details
        </h1>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 mb-4">
            Assignment ID: <code className="text-sm">{assignmentId}</code>
          </p>
          <p className="text-gray-500">
            Assignment details and start assessment functionality will be
            implemented here.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AssignmentDetailPage;
