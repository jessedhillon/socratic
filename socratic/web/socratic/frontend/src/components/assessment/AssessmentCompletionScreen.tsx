import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { ChatMessageData } from './ChatMessage';

export type CompletionStep =
  | 'stopping'
  | 'uploading'
  | 'completing'
  | 'complete'
  | 'error';

export interface AssessmentSummary {
  objectiveTitle: string;
  startedAt: string;
  completedAt: string;
  messageCount: number;
  learnerResponseCount: number;
  duration: number; // in seconds
}

export interface AssessmentCompletionScreenProps {
  /** Assessment summary data */
  summary: AssessmentSummary;
  /** Current completion step */
  step: CompletionStep;
  /** Upload progress percentage (0-100) */
  uploadProgress?: number;
  /** Error message if completion failed */
  error?: string | null;
  /** Callback to retry completion */
  onRetry?: () => void;
  /** Callback to return to assignments */
  onReturn?: () => void;
  /** Messages from the conversation (for review) */
  messages?: ChatMessageData[];
}

/**
 * Assessment completion screen showing the post-assessment flow.
 *
 * Displays:
 * 1. Progress indicators for stopping recording, uploading video, completing
 * 2. Summary of the assessment (duration, responses, etc.)
 * 3. Success confirmation with return button
 * 4. Error state with retry option
 */
export function AssessmentCompletionScreen({
  summary,
  step,
  uploadProgress = 0,
  error = null,
  onRetry,
  onReturn,
  messages = [],
}: AssessmentCompletionScreenProps): React.ReactElement {
  const navigate = useNavigate();
  const [showTranscript, setShowTranscript] = useState(false);

  const handleReturn = useCallback(() => {
    if (onReturn) {
      onReturn();
    } else {
      navigate('/assignments');
    }
  }, [navigate, onReturn]);

  // Format duration as mm:ss
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Format relative time
  const formatTime = (isoString: string): string => {
    return new Date(isoString).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Progress step display
  const getStepInfo = (currentStep: CompletionStep) => {
    const steps = [
      {
        id: 'stopping',
        label: 'Stopping Recording',
        icon: '📹',
        description: 'Finalizing video recording...',
      },
      {
        id: 'uploading',
        label: 'Uploading Video',
        icon: '☁️',
        description: `Uploading to secure storage... ${uploadProgress}%`,
      },
      {
        id: 'completing',
        label: 'Saving Assessment',
        icon: '💾',
        description: 'Submitting your responses...',
      },
    ];

    const currentIndex = steps.findIndex((s) => s.id === currentStep);
    return steps.map((s, i) => ({
      ...s,
      status:
        i < currentIndex
          ? 'complete'
          : i === currentIndex
            ? 'current'
            : 'pending',
    }));
  };

  const stepInfo = getStepInfo(step);

  // Error state
  if (step === 'error') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-8 h-8 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Submission Failed
          </h2>
          <p className="text-gray-600 mb-6">
            {error ||
              'There was a problem submitting your assessment. Your recording has been saved locally.'}
          </p>
          <div className="flex gap-3 justify-center">
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                Try Again
              </button>
            )}
            <button
              onClick={handleReturn}
              className="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors"
            >
              Return to Assignments
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Progress state (stopping, uploading, completing)
  if (step !== 'complete') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full">
          <h2 className="text-xl font-semibold text-gray-900 mb-6 text-center">
            Completing Assessment
          </h2>

          {/* Progress steps */}
          <div className="space-y-4 mb-8">
            {stepInfo.map((item, index) => (
              <div
                key={item.id}
                className={`flex items-center gap-4 ${
                  item.status === 'pending' ? 'opacity-50' : ''
                }`}
              >
                {/* Step indicator */}
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-lg ${
                    item.status === 'complete'
                      ? 'bg-green-100 text-green-600'
                      : item.status === 'current'
                        ? 'bg-blue-100 text-blue-600'
                        : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {item.status === 'complete' ? (
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
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  ) : item.status === 'current' ? (
                    <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <span className="text-sm">{index + 1}</span>
                  )}
                </div>

                {/* Step text */}
                <div className="flex-1">
                  <div
                    className={`font-medium ${
                      item.status === 'current'
                        ? 'text-blue-600'
                        : 'text-gray-900'
                    }`}
                  >
                    {item.label}
                  </div>
                  {item.status === 'current' && (
                    <div className="text-sm text-gray-500">
                      {item.description}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Upload progress bar */}
          {step === 'uploading' && (
            <div className="mb-4">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          <p className="text-center text-gray-500 text-sm">
            Please don't close this window until the submission is complete.
          </p>
        </div>
      </div>
    );
  }

  // Complete state
  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Success header */}
        <div className="bg-white rounded-xl shadow-lg p-8 mb-6 text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-10 h-10 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Assessment Complete!
          </h1>
          <p className="text-gray-600">
            Your responses have been submitted for review.
          </p>
        </div>

        {/* Summary card */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary</h2>

          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Assessment</span>
              <span className="font-medium text-gray-900">
                {summary.objectiveTitle}
              </span>
            </div>

            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Duration</span>
              <span className="font-medium text-gray-900">
                {formatDuration(summary.duration)}
              </span>
            </div>

            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Started</span>
              <span className="font-medium text-gray-900">
                {formatTime(summary.startedAt)}
              </span>
            </div>

            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Completed</span>
              <span className="font-medium text-gray-900">
                {formatTime(summary.completedAt)}
              </span>
            </div>

            <div className="flex justify-between items-center py-2">
              <span className="text-gray-600">Your Responses</span>
              <span className="font-medium text-gray-900">
                {summary.learnerResponseCount}
              </span>
            </div>
          </div>
        </div>

        {/* Transcript preview (collapsible) */}
        {messages.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
            <button
              onClick={() => setShowTranscript(!showTranscript)}
              className="w-full flex items-center justify-between"
            >
              <h2 className="text-lg font-semibold text-gray-900">
                Conversation Transcript
              </h2>
              <svg
                className={`w-5 h-5 text-gray-500 transition-transform ${
                  showTranscript ? 'rotate-180' : ''
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {showTranscript && (
              <div className="mt-4 space-y-4 max-h-96 overflow-y-auto">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`p-3 rounded-lg ${
                      msg.type === 'learner'
                        ? 'bg-blue-50 ml-8'
                        : msg.type === 'interviewer'
                          ? 'bg-gray-50 mr-8'
                          : 'bg-yellow-50 mx-4 text-center text-sm'
                    }`}
                  >
                    <div className="text-xs text-gray-500 mb-1">
                      {msg.type === 'learner'
                        ? 'You'
                        : msg.type === 'interviewer'
                          ? 'Interviewer'
                          : 'System'}
                    </div>
                    <div className="text-gray-800 whitespace-pre-wrap">
                      {msg.content}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Next steps */}
        <div className="bg-blue-50 rounded-xl p-6 mb-6">
          <h3 className="font-semibold text-blue-900 mb-2">What's Next?</h3>
          <p className="text-blue-800 text-sm">
            Your instructor will review your assessment and provide feedback.
            You'll receive a notification when your results are available.
          </p>
        </div>

        {/* Return button */}
        <div className="text-center">
          <button
            onClick={handleReturn}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
          >
            Return to Assignments
          </button>
        </div>
      </div>
    </div>
  );
}

export default AssessmentCompletionScreen;
