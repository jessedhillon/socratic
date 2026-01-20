import React from 'react';
import { Link } from 'react-router-dom';

/**
 * 404 Not Found page.
 */
const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-300 mb-4">404</h1>
        <p className="text-xl text-gray-600 mb-6">Page not found</p>
        <Link
          to="/assignments"
          className="text-blue-600 hover:text-blue-800 underline"
        >
          Go to Assignments
        </Link>
      </div>
    </div>
  );
};

export default NotFoundPage;
