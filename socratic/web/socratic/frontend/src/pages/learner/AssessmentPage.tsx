import React, {
  useEffect,
  useCallback,
  useRef,
  useState,
  useMemo,
} from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  VoiceConversationLoop,
  useAssessmentState,
  useAssessmentApi,
  AssessmentCompletionScreen,
  type CompletionStep,
  type AssessmentSummary,
} from '../../components/assessment';
import { RecordingStatusOverlay } from '../../components/RecordingStatusOverlay';
import { PermissionGate } from '../../components/PermissionGate';
import { CameraPreview } from '../../components/CameraPreview';
import { useRecordingSession } from '../../hooks/useRecordingSession';
import { completeAssessment as completeAssessmentApi } from '../../api/sdk.gen';

/**
 * Assessment page - where learners complete their assessments.
 *
 * This page manages the full assessment flow:
 * 1. Initialize assignment
 * 2. Request permissions (PermissionGate)
 * 3. Show camera preview and confirm ready
 * 4. Turn-based conversation with AI (recording active)
 * 5. Completion with summary and confirmation
 */
const AssessmentPage: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const { state, actions } = useAssessmentState();
  const api = useAssessmentApi();

  // Recording session for video/audio capture
  const {
    sessionState,
    stream,
    duration,
    isPausedByVisibility,
    initialize: initializeRecording,
    startRecording,
    abandon: abandonRecording,
  } = useRecordingSession({
    pauseOnHidden: true,
    autoStart: false,
  });

  // Keep a ref to the abandon function for cleanup on unmount
  const abandonRef = useRef(abandonRecording);
  abandonRef.current = abandonRecording;

  // Cleanup recording session on unmount (e.g., navigation away)
  useEffect(() => {
    return () => {
      abandonRef.current();
    };
  }, []);

  // Completion state
  const [completionStep, setCompletionStep] = useState<CompletionStep | null>(
    null
  );
  const [completionError, setCompletionError] = useState<string | null>(null);
  const [completedAt, setCompletedAt] = useState<string | null>(null);

  // Track streamed content for the current message
  const streamedContentRef = useRef('');

  // Track if user has confirmed ready to start
  const [isStartingAssessment, setIsStartingAssessment] = useState(false);

  // Initialize assessment state when component mounts
  useEffect(() => {
    if (assignmentId && state.phase === 'idle') {
      actions.initialize(assignmentId);
    }
  }, [assignmentId, state.phase, actions]);

  // Handle permission granted - transition to ready state
  const handlePermissionsGranted = useCallback(async () => {
    // Initialize the recording session (acquires stream but doesn't record)
    await initializeRecording();
    // Transition to ready state
    actions.grantPermissions();
  }, [initializeRecording, actions]);

  // Handle "I'm Ready" button click - start assessment and recording
  const handleStartAssessment = useCallback(async () => {
    if (!state.assignmentId || isStartingAssessment) return;

    setIsStartingAssessment(true);

    try {
      // Start recording first
      await startRecording();

      // Create a streaming message placeholder
      streamedContentRef.current = '';
      const messageId = actions.addInterviewerMessage('', true);

      // Start the assessment API call
      const result = await api.startAssessment(state.assignmentId, (token) => {
        streamedContentRef.current += token;
        actions.updateStreamingMessage(messageId, streamedContentRef.current);
      });

      // Finalize the message
      actions.finishStreamingMessage(messageId);
      actions.startAssessment(result.attemptId, result.objectiveTitle);
      actions.responseComplete();
    } catch (err) {
      console.error('Failed to start assessment:', err);
      actions.setError('Failed to start assessment. Please try again.');
    } finally {
      setIsStartingAssessment(false);
    }
  }, [state.assignmentId, isStartingAssessment, startRecording, actions, api]);

  // Handle sending messages
  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!state.attemptId) return;

      // Add learner message and mark as waiting
      actions.sendMessage(content);

      try {
        // Create a streaming message placeholder
        streamedContentRef.current = '';
        const messageId = actions.addInterviewerMessage('', true);

        await api.sendMessage(state.attemptId, content, (token) => {
          // Update streaming message with each token
          streamedContentRef.current += token;
          actions.updateStreamingMessage(messageId, streamedContentRef.current);
        });

        // Finalize the message
        actions.finishStreamingMessage(messageId);
        actions.responseComplete();

        // TODO: Check for completion signal from backend
        // The backend should signal when the assessment is complete
      } catch (err) {
        console.error('Failed to send message:', err);
        actions.setError('Failed to send message. Please try again.');
      }
    },
    [state.attemptId, actions, api]
  );

  // Handle completing the assessment
  const handleCompleteAssessment = useCallback(async () => {
    if (!state.attemptId) return;

    setCompletionStep('stopping');
    setCompletionError(null);
    actions.beginCompletion();

    try {
      // Step 1: Stop recording (simulated - actual implementation in SOC-123)
      setCompletionStep('uploading');

      // Step 2: Upload video (simulated - actual implementation in SOC-123)
      // In real implementation, this would upload the video blob to S3
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Step 3: Complete assessment via API
      setCompletionStep('completing');
      const response = await completeAssessmentApi({
        path: { attempt_id: state.attemptId },
        body: { feedback: null },
      });

      if (response.error) {
        throw new Error('Failed to complete assessment');
      }

      // Success!
      setCompletedAt(response.data.completed_at);
      setCompletionStep('complete');
      actions.completeAssessment();
    } catch (err) {
      console.error('Failed to complete assessment:', err);
      setCompletionStep('error');
      setCompletionError(
        err instanceof Error
          ? err.message
          : 'An error occurred while completing your assessment.'
      );
    }
  }, [state.attemptId, actions]);

  // Handle retry completion
  const handleRetryCompletion = useCallback(() => {
    setCompletionStep(null);
    setCompletionError(null);
  }, []);

  // Calculate assessment summary
  const assessmentSummary = useMemo<AssessmentSummary | null>(() => {
    if (!state.startedAt || !state.objectiveTitle) return null;

    const startTime = new Date(state.startedAt).getTime();
    const endTime = completedAt ? new Date(completedAt).getTime() : Date.now();
    const durationMs = Math.floor((endTime - startTime) / 1000);

    const learnerMessages = state.messages.filter((m) => m.type === 'learner');

    return {
      objectiveTitle: state.objectiveTitle,
      startedAt: state.startedAt,
      completedAt: completedAt || new Date().toISOString(),
      messageCount: state.messages.length,
      learnerResponseCount: learnerMessages.length,
      duration: durationMs,
    };
  }, [state.startedAt, state.objectiveTitle, state.messages, completedAt]);

  // Render completion screen
  if (completionStep !== null && assessmentSummary) {
    return (
      <AssessmentCompletionScreen
        summary={assessmentSummary}
        step={completionStep}
        uploadProgress={completionStep === 'uploading' ? 75 : 100}
        error={completionError}
        onRetry={handleRetryCompletion}
        messages={state.messages}
      />
    );
  }

  // Render loading state
  if (state.phase === 'idle') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading assessment...</p>
        </div>
      </div>
    );
  }

  // Render permission request state
  if (state.phase === 'initializing') {
    return (
      <div className="h-full flex flex-col">
        <header className="bg-white border-b px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              to="/assignments"
              className="text-gray-500 hover:text-gray-700"
            >
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
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
            <h1 className="text-xl font-semibold text-gray-800">
              Assessment Setup
            </h1>
          </div>
        </header>

        <div className="flex-1 flex items-center justify-center bg-gray-50">
          <div className="max-w-md w-full">
            <PermissionGate
              camera
              microphone
              onGranted={handlePermissionsGranted}
              title="Camera & Microphone Required"
              description="This assessment requires access to your camera and microphone. Your session will be recorded for instructor review."
            >
              {/* This won't render until permissions are granted */}
              <div />
            </PermissionGate>
          </div>
        </div>
      </div>
    );
  }

  // Render ready state - camera preview and start button
  if (state.phase === 'ready') {
    return (
      <div className="h-full flex flex-col">
        <header className="bg-white border-b px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              to="/assignments"
              className="text-gray-500 hover:text-gray-700"
            >
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
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
            <h1 className="text-xl font-semibold text-gray-800">
              Ready to Begin
            </h1>
          </div>
        </header>

        <div className="flex-1 flex items-center justify-center bg-gray-50">
          <div className="max-w-lg w-full mx-4">
            <div className="bg-white rounded-xl shadow-lg p-8">
              {/* Camera preview */}
              <div className="mb-6">
                <h2 className="text-lg font-medium text-gray-800 mb-3">
                  Camera Preview
                </h2>
                <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
                  {stream ? (
                    <video
                      autoPlay
                      playsInline
                      muted
                      ref={(el) => {
                        if (el && stream) {
                          el.srcObject = stream;
                        }
                      }}
                      className="w-full h-full object-cover"
                      style={{ transform: 'scaleX(-1)' }}
                    />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white" />
                    </div>
                  )}
                </div>
                <p className="text-sm text-gray-500 mt-2">
                  Make sure you're in a well-lit area and your face is visible.
                </p>
              </div>

              {/* Instructions */}
              <div className="mb-6 p-4 bg-blue-50 rounded-lg">
                <h3 className="font-medium text-blue-800 mb-2">
                  Before you begin
                </h3>
                <ul className="text-sm text-blue-700 space-y-1">
                  <li className="flex items-start gap-2">
                    <svg
                      className="w-4 h-4 mt-0.5 flex-shrink-0"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Find a quiet space where you won't be interrupted
                  </li>
                  <li className="flex items-start gap-2">
                    <svg
                      className="w-4 h-4 mt-0.5 flex-shrink-0"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Recording will begin when you click "I'm Ready"
                  </li>
                  <li className="flex items-start gap-2">
                    <svg
                      className="w-4 h-4 mt-0.5 flex-shrink-0"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Speak clearly and take your time with responses
                  </li>
                </ul>
              </div>

              {/* Start button */}
              <button
                onClick={handleStartAssessment}
                disabled={isStartingAssessment || !stream}
                className="w-full px-6 py-4 bg-blue-600 text-white text-lg font-medium rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isStartingAssessment ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                    Starting Assessment...
                  </>
                ) : (
                  <>
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
                        d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    I'm Ready - Begin Assessment
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render error state
  if (state.phase === 'error') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-lg font-medium mb-4">
            {state.error}
          </div>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => actions.clearError()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Try Again
            </button>
            <Link
              to="/assignments"
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
            >
              Back to Assignments
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Render completed state (legacy - now uses completion screen)
  if (state.phase === 'completed') {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <header className="bg-white border-b px-6 py-4">
          <h1 className="text-xl font-semibold text-gray-800">
            {state.objectiveTitle || 'Assessment'}
          </h1>
          <p className="text-sm text-green-600">Assessment Complete</p>
        </header>

        {/* Show final conversation */}
        <div className="flex-1 overflow-hidden">
          <VoiceConversationLoop
            messages={state.messages}
            onSendMessage={() => {}}
            isWaitingForResponse={false}
            isAssessmentComplete={true}
            autoPlayResponses={false}
          />
        </div>

        {/* Completion actions */}
        <div className="bg-white border-t px-6 py-4">
          <div className="max-w-3xl mx-auto text-center">
            <p className="text-gray-600 mb-4">
              Your responses have been submitted for review. You'll receive
              feedback from your instructor soon.
            </p>
            <button
              onClick={() => navigate('/assignments')}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Return to Assignments
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render active assessment (in_progress or completing)
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">
            {state.objectiveTitle || 'Assessment'}
          </h1>
          <p className="text-sm text-gray-500">
            Assessment in progress
            {state.startedAt && (
              <>
                {' '}
                &middot; Started{' '}
                {new Date(state.startedAt).toLocaleTimeString()}
              </>
            )}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Recording status overlay */}
          <RecordingStatusOverlay
            isRecording={sessionState === 'recording'}
            isPaused={sessionState === 'paused'}
            durationSeconds={duration}
            isPausedByVisibility={isPausedByVisibility}
            stream={stream}
            showAudioLevel
          />

          {/* Complete button */}
          <button
            onClick={handleCompleteAssessment}
            disabled={
              state.isWaitingForResponse || state.phase === 'completing'
            }
            className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            Complete Assessment
          </button>
        </div>
      </header>

      {/* Voice conversation interface */}
      <div className="flex-1 overflow-hidden">
        <VoiceConversationLoop
          messages={state.messages}
          onSendMessage={handleSendMessage}
          isWaitingForResponse={state.isWaitingForResponse}
          isAssessmentComplete={state.phase === 'completing'}
          autoPlayResponses
          voice="nova"
          speechSpeed={1.1}
        />
      </div>

      {/* Camera preview (minimizable) */}
      <CameraPreview
        stream={stream}
        isRecording={sessionState === 'recording'}
        hasAudio
        position="bottom-right"
        defaultMinimized={false}
      />
    </div>
  );
};

export default AssessmentPage;
