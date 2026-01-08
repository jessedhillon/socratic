import React from 'react';

interface ReviewSummary {
  attempt_id: string;
  learner_id: string;
  learner_name: string | null;
  objective_id: string;
  objective_title: string;
  grade: string | null;
  confidence_score: number | null;
  flags: string[];
  completed_at: string | null;
}

interface ReviewListProps {
  reviews: ReviewSummary[];
  onSelectReview: (attemptId: string) => void;
  selectedAttemptId?: string;
}

const gradeColors: Record<string, string> = {
  S: 'bg-green-100 text-green-800',
  A: 'bg-blue-100 text-blue-800',
  C: 'bg-yellow-100 text-yellow-800',
  F: 'bg-red-100 text-red-800',
};

const flagColors: Record<string, string> = {
  HighFluencyLowSubstance: 'bg-orange-100 text-orange-800',
  RepeatedEvasion: 'bg-red-100 text-red-800',
  VocabularyMirroring: 'bg-purple-100 text-purple-800',
  InconsistentReasoning: 'bg-pink-100 text-pink-800',
  PossibleGaming: 'bg-red-200 text-red-900',
  LowConfidence: 'bg-gray-100 text-gray-800',
};

/**
 * List of reviews pending educator attention.
 */
const ReviewList: React.FC<ReviewListProps> = ({
  reviews,
  onSelectReview,
  selectedAttemptId,
}) => {
  if (reviews.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No reviews pending. All assessments have been reviewed.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {reviews.map((review) => (
        <button
          key={review.attempt_id}
          onClick={() => onSelectReview(review.attempt_id)}
          className={`w-full text-left p-4 rounded-lg border transition-colors ${
            selectedAttemptId === review.attempt_id
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
          }`}
        >
          <div className="flex justify-between items-start">
            <div>
              <h4 className="font-medium text-gray-900">
                {review.learner_name || 'Unknown Learner'}
              </h4>
              <p className="text-sm text-gray-600">{review.objective_title}</p>
            </div>
            <div className="flex items-center gap-2">
              {review.grade && (
                <span
                  className={`px-2 py-1 rounded text-sm font-medium ${
                    gradeColors[review.grade] || 'bg-gray-100'
                  }`}
                >
                  {review.grade}
                </span>
              )}
              {review.confidence_score !== null && (
                <span className="text-xs text-gray-500">
                  {Math.round(review.confidence_score * 100)}%
                </span>
              )}
            </div>
          </div>

          {review.flags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {review.flags.map((flag) => (
                <span
                  key={flag}
                  className={`px-2 py-0.5 rounded text-xs ${
                    flagColors[flag] || 'bg-gray-100 text-gray-700'
                  }`}
                >
                  {flag.replace(/([A-Z])/g, ' $1').trim()}
                </span>
              ))}
            </div>
          )}

          {review.completed_at && (
            <p className="mt-2 text-xs text-gray-400">
              Completed {new Date(review.completed_at).toLocaleDateString()}
            </p>
          )}
        </button>
      ))}
    </div>
  );
};

export default ReviewList;
