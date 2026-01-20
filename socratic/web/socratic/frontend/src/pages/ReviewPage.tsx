import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  listPendingReviews,
  getReviewDetail,
  acceptGrade,
  overrideGrade,
} from '../api';
import type { ReviewSummary, ReviewDetailResponse, Grade } from '../api';
import { getLoginUrl } from '../auth';
import ReviewList from '../components/ReviewList';
import TranscriptViewer from '../components/TranscriptViewer';
import EvidencePanel from '../components/EvidencePanel';

const gradeColors: Record<string, string> = {
  S: 'bg-green-500',
  A: 'bg-blue-500',
  C: 'bg-yellow-500',
  F: 'bg-red-500',
};

/**
 * Educator review page for assessing completed attempts.
 */
const ReviewPage: React.FC = () => {
  const { attemptId } = useParams<{ attemptId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [selectedReview, setSelectedReview] =
    useState<ReviewDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [highlightedCriterion, setHighlightedCriterion] = useState<
    string | null
  >(null);

  const [overrideGradeValue, setOverrideGradeValue] = useState<string>('');
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Fetch pending reviews
  useEffect(() => {
    fetchReviews();
  }, []);

  // Fetch selected review detail
  useEffect(() => {
    if (attemptId) {
      fetchReviewDetailData(attemptId);
    } else {
      setSelectedReview(null);
    }
  }, [attemptId]);

  const fetchReviews = async () => {
    try {
      const { data, response } = await listPendingReviews();
      if (!response.ok) {
        if (response.status === 401) {
          navigate(getLoginUrl(location.pathname));
          return;
        }
        throw new Error('Failed to fetch reviews');
      }
      setReviews(data?.reviews ?? []);
    } catch (err) {
      console.error('Failed to fetch reviews:', err);
      setError('Failed to load reviews');
    } finally {
      setLoading(false);
    }
  };

  const fetchReviewDetailData = async (id: string) => {
    try {
      const { data, response } = await getReviewDetail({
        path: { attempt_id: id },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch review detail');
      }
      setSelectedReview(data ?? null);
    } catch (err) {
      console.error('Failed to fetch review detail:', err);
    }
  };

  const handleSelectReview = (id: string) => {
    navigate(`/reviews/${id}`);
  };

  const handleAcceptGrade = async () => {
    if (!selectedReview) return;

    setSubmitting(true);
    try {
      const { response } = await acceptGrade({
        path: { attempt_id: selectedReview.attempt.attempt_id },
        body: {},
      });
      if (!response.ok) {
        throw new Error('Failed to accept grade');
      }
      // Refresh reviews and detail
      await fetchReviews();
      await fetchReviewDetailData(selectedReview.attempt.attempt_id);
    } catch (err) {
      console.error('Failed to accept grade:', err);
      alert('Failed to accept grade');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOverrideGrade = async () => {
    if (!selectedReview || !overrideGradeValue || !overrideReason) return;

    setSubmitting(true);
    try {
      const { response } = await overrideGrade({
        path: { attempt_id: selectedReview.attempt.attempt_id },
        body: {
          new_grade: overrideGradeValue as Grade,
          reason: overrideReason,
        },
      });
      if (!response.ok) {
        throw new Error('Failed to override grade');
      }
      // Refresh and reset form
      await fetchReviews();
      await fetchReviewDetailData(selectedReview.attempt.attempt_id);
      setShowOverrideForm(false);
      setOverrideGradeValue('');
      setOverrideReason('');
    } catch (err) {
      console.error('Failed to override grade:', err);
      alert('Failed to override grade');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Loading reviews...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">
        Assessment Reviews
      </h1>

      <div className="grid grid-cols-12 gap-6">
        {/* Reviews List */}
        <div className="col-span-3 bg-white rounded-lg shadow p-4 h-[calc(100vh-12rem)] overflow-y-auto">
          <h2 className="font-semibold text-gray-700 mb-4">
            Pending Reviews ({reviews.length})
          </h2>
          <ReviewList
            reviews={reviews}
            onSelectReview={handleSelectReview}
            selectedAttemptId={attemptId}
          />
        </div>

        {/* Review Detail */}
        <div className="col-span-9">
          {selectedReview ? (
            <div className="grid grid-cols-2 gap-6">
              {/* Transcript */}
              <div className="bg-white rounded-lg shadow p-4 h-[calc(100vh-12rem)] overflow-y-auto">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="font-semibold text-gray-700">Transcript</h2>
                  <div className="flex items-center gap-2">
                    {selectedReview.attempt.grade && (
                      <span
                        className={`px-3 py-1 rounded text-white font-medium ${
                          gradeColors[selectedReview.attempt.grade] ||
                          'bg-gray-500'
                        }`}
                      >
                        Grade: {selectedReview.attempt.grade}
                      </span>
                    )}
                    {selectedReview.attempt.confidence_score !== null && (
                      <span className="text-sm text-gray-500">
                        (
                        {Math.round(
                          parseFloat(selectedReview.attempt.confidence_score) *
                            100
                        )}
                        % confidence)
                      </span>
                    )}
                  </div>
                </div>

                <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                  <h3 className="font-medium text-gray-800">
                    {selectedReview.objective_title}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {selectedReview.objective_description}
                  </p>
                  <p className="text-xs text-gray-400 mt-2">
                    Learner: {selectedReview.attempt.learner_name || 'Unknown'}
                  </p>
                </div>

                <TranscriptViewer
                  segments={selectedReview.transcript}
                  evidenceMappings={
                    selectedReview.evaluation?.evidence_mappings
                  }
                  highlightedCriterion={highlightedCriterion || undefined}
                />
              </div>

              {/* Evidence & Actions */}
              <div className="bg-white rounded-lg shadow p-4 h-[calc(100vh-12rem)] overflow-y-auto">
                <h2 className="font-semibold text-gray-700 mb-4">
                  Evaluation Details
                </h2>

                {selectedReview.evaluation ? (
                  <>
                    <EvidencePanel
                      evidenceMappings={
                        selectedReview.evaluation.evidence_mappings
                      }
                      strengths={selectedReview.evaluation.strengths}
                      gaps={selectedReview.evaluation.gaps}
                      reasoningSummary={
                        selectedReview.evaluation.reasoning_summary
                      }
                      flags={selectedReview.evaluation.flags}
                      onCriterionHover={setHighlightedCriterion}
                      highlightedCriterion={highlightedCriterion || undefined}
                    />

                    {/* Override History */}
                    {selectedReview.override_history.length > 0 && (
                      <div className="mt-6">
                        <h3 className="font-semibold text-gray-800 mb-3">
                          Override History
                        </h3>
                        <div className="space-y-2">
                          {selectedReview.override_history.map((override) => (
                            <div
                              key={override.override_id}
                              className="border border-gray-200 rounded p-3 text-sm"
                            >
                              <div className="flex justify-between">
                                <span className="font-medium">
                                  {override.educator_name || 'Educator'}
                                </span>
                                <span className="text-gray-500">
                                  {new Date(
                                    override.create_time
                                  ).toLocaleString()}
                                </span>
                              </div>
                              <p className="text-gray-600 mt-1">
                                Changed grade from{' '}
                                {override.original_grade || 'N/A'} to{' '}
                                {override.new_grade}
                              </p>
                              <p className="text-gray-500 mt-1">
                                {override.reason}
                              </p>
                              {override.feedback && (
                                <p className="text-gray-600 mt-2 italic">
                                  "{override.feedback}"
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    {selectedReview.attempt.status === 'evaluated' && (
                      <div className="mt-6 pt-6 border-t border-gray-200">
                        <h3 className="font-semibold text-gray-800 mb-3">
                          Actions
                        </h3>
                        {!showOverrideForm ? (
                          <div className="flex gap-3">
                            <button
                              onClick={handleAcceptGrade}
                              disabled={submitting}
                              className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                            >
                              {submitting ? 'Processing...' : 'Accept Grade'}
                            </button>
                            <button
                              onClick={() => setShowOverrideForm(true)}
                              disabled={submitting}
                              className="flex-1 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50"
                            >
                              Override Grade
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">
                                New Grade
                              </label>
                              <select
                                value={overrideGradeValue}
                                onChange={(e) =>
                                  setOverrideGradeValue(e.target.value)
                                }
                                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                              >
                                <option value="">Select grade...</option>
                                <option value="S">S - Superb</option>
                                <option value="A">A - Advanced</option>
                                <option value="C">C - Developing</option>
                                <option value="F">F - Beginning</option>
                              </select>
                            </div>
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">
                                Reason for Override
                              </label>
                              <textarea
                                value={overrideReason}
                                onChange={(e) =>
                                  setOverrideReason(e.target.value)
                                }
                                rows={3}
                                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                placeholder="Explain why you're overriding the AI grade..."
                              />
                            </div>
                            <div className="flex gap-3">
                              <button
                                onClick={handleOverrideGrade}
                                disabled={
                                  submitting ||
                                  !overrideGradeValue ||
                                  overrideReason.length < 10
                                }
                                className="flex-1 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50"
                              >
                                {submitting
                                  ? 'Submitting...'
                                  : 'Submit Override'}
                              </button>
                              <button
                                onClick={() => {
                                  setShowOverrideForm(false);
                                  setOverrideGradeValue('');
                                  setOverrideReason('');
                                }}
                                disabled={submitting}
                                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    No evaluation data available
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              Select a review from the list to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReviewPage;
