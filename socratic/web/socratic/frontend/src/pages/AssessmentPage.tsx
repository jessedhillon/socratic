import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Assessment from '../components/Assessment';

/**
 * Assessment page that wraps the Assessment component.
 * Handles routing and URL parameter extraction.
 */
const AssessmentPage: React.FC = () => {
  const { assignmentId, attemptId } = useParams<{
    assignmentId: string;
    attemptId?: string;
  }>();
  const navigate = useNavigate();

  if (!assignmentId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-500">Assignment ID is required</div>
      </div>
    );
  }

  const handleAttemptCreated = (newAttemptId: string) => {
    // Update URL with attempt ID without full page reload
    navigate(`/assessment/${assignmentId}/attempt/${newAttemptId}`, {
      replace: true,
    });
  };

  const handleComplete = () => {
    // Navigate back to dashboard after completion
    setTimeout(() => {
      navigate('/');
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gray-100 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-4">
          <button
            onClick={() => navigate('/')}
            className="text-gray-600 hover:text-gray-800 flex items-center gap-1"
          >
            <span>&larr;</span>
            <span>Back to Dashboard</span>
          </button>
        </div>
        <div className="h-[calc(100vh-8rem)]">
          <Assessment
            assignmentId={assignmentId}
            attemptId={attemptId}
            onAttemptCreated={handleAttemptCreated}
            onComplete={handleComplete}
          />
        </div>
      </div>
    </div>
  );
};

export default AssessmentPage;
