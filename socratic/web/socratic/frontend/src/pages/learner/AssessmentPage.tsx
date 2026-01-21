import React, {
  useEffect,
  useCallback,
  useRef,
  useState,
  useMemo,
} from 'react';
import {
  useParams,
  useNavigate,
  Link,
  useSearchParams,
} from 'react-router-dom';
import {
  VoiceConversationLoop,
  useAssessmentState,
  useAssessmentApi,
  AssessmentCompletionScreen,
  type CompletionStep,
  type AssessmentSummary,
  type ConversationTurn,
} from '../../components/assessment';
import { RecordingStatusOverlay } from '../../components/RecordingStatusOverlay';
import { PermissionGate } from '../../components/PermissionGate';
import { CameraPreview } from '../../components/CameraPreview';
import { TabVisibilityWarning } from '../../components/TabVisibilityWarning';
import { NavigationConfirmDialog } from '../../components/NavigationConfirmDialog';
import { useRecordingSession } from '../../hooks/useRecordingSession';
import { useNavigationGuard } from '../../hooks/useNavigationGuard';
import {
  completeAssessment as completeAssessmentApi,
  uploadAssessmentVideo,
} from '../../api/sdk.gen';

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
// Mock messages for testing closure_ready state
const MOCK_MESSAGES = [
  {
    id: 'mock-1',
    type: 'interviewer' as const,
    content:
      "Hello! Let's talk about ratios and proportional reasoning. Can you tell me, in your own words, what a ratio is?",
    timestamp: new Date(Date.now() - 600000).toISOString(),
  },
  {
    id: 'mock-2',
    type: 'learner' as const,
    content:
      'A ratio is a way to compare two quantities, like saying there are 3 apples for every 2 oranges.',
    timestamp: new Date(Date.now() - 570000).toISOString(),
  },
  {
    id: 'mock-3',
    type: 'interviewer' as const,
    content:
      "That's a good start! How would you explain the difference between a ratio and a fraction?",
    timestamp: new Date(Date.now() - 540000).toISOString(),
  },
  {
    id: 'mock-4',
    type: 'learner' as const,
    content:
      "I think they're related but a fraction is part of a whole, while a ratio compares two separate things. Like if I have a pizza cut into 8 slices and I eat 3, that's a fraction - 3/8 of the pizza. But if I'm comparing how many slices I ate versus how many my friend ate, that's more of a ratio.",
    timestamp: new Date(Date.now() - 510000).toISOString(),
  },
  {
    id: 'mock-5',
    type: 'interviewer' as const,
    content:
      "Excellent example with the pizza! You're showing good intuition there. Now, let's explore proportional relationships. If a recipe calls for 2 cups of flour for every 3 cups of sugar, and you want to use 6 cups of flour, how much sugar would you need?",
    timestamp: new Date(Date.now() - 480000).toISOString(),
  },
  {
    id: 'mock-6',
    type: 'learner' as const,
    content:
      "Okay, so if 2 cups of flour goes with 3 cups of sugar, and I'm tripling the flour to 6 cups, I'd need to triple the sugar too. So that would be 9 cups of sugar.",
    timestamp: new Date(Date.now() - 450000).toISOString(),
  },
  {
    id: 'mock-7',
    type: 'interviewer' as const,
    content:
      "Perfect! You recognized that you needed to scale both quantities by the same factor. That's the heart of proportional reasoning. Can you think of a real-world situation where understanding ratios and proportions would be important?",
    timestamp: new Date(Date.now() - 420000).toISOString(),
  },
  {
    id: 'mock-8',
    type: 'learner' as const,
    content:
      "Maybe like when you're mixing paint colors? If you want to make a certain shade of green, you need to mix blue and yellow in the right ratio. And if you want more paint, you have to keep the same ratio or the color will be different.",
    timestamp: new Date(Date.now() - 390000).toISOString(),
  },
  {
    id: 'mock-9',
    type: 'interviewer' as const,
    content:
      "That's a fantastic real-world application! Artists and designers use proportional reasoning all the time. Let me ask you something a bit more challenging: if you're driving at 60 miles per hour, how far will you travel in 2.5 hours?",
    timestamp: new Date(Date.now() - 360000).toISOString(),
  },
  {
    id: 'mock-10',
    type: 'learner' as const,
    content:
      "So 60 miles per hour means 60 miles in 1 hour. For 2.5 hours, I'd multiply 60 times 2.5, which is... 150 miles.",
    timestamp: new Date(Date.now() - 330000).toISOString(),
  },
  {
    id: 'mock-11',
    type: 'interviewer' as const,
    content:
      "Correct! You're applying the concept of unit rates there - miles per hour is a rate that tells you the ratio of distance to time. Now, here's a question that requires a bit more thought: if 4 workers can build a wall in 6 days, how long would it take 3 workers to build the same wall?",
    timestamp: new Date(Date.now() - 300000).toISOString(),
  },
  {
    id: 'mock-12',
    type: 'learner' as const,
    content:
      "Hmm, this one is tricky. If you have fewer workers, it takes longer... So it's not a direct proportion. Let me think. 4 workers times 6 days is 24 worker-days of work total. So with 3 workers, it would be 24 divided by 3, which is 8 days.",
    timestamp: new Date(Date.now() - 270000).toISOString(),
  },
  {
    id: 'mock-13',
    type: 'interviewer' as const,
    content:
      "Excellent reasoning! You identified that this is an inverse proportion - as the number of workers decreases, the time increases. You used the concept of 'worker-days' which is a sophisticated way to think about the total work needed. That shows strong proportional reasoning skills.",
    timestamp: new Date(Date.now() - 240000).toISOString(),
  },
  {
    id: 'mock-14',
    type: 'learner' as const,
    content:
      "Thanks! I wasn't sure at first but thinking about the total work helped me figure it out.",
    timestamp: new Date(Date.now() - 210000).toISOString(),
  },
  {
    id: 'mock-15',
    type: 'interviewer' as const,
    content:
      "Thank you for sharing your thoughts today! You've demonstrated a solid understanding of ratios and proportional reasoning. You correctly identified that ratios compare quantities, distinguished them from fractions with a great pizza example, successfully scaled recipes, applied unit rates to distance problems, and even handled inverse proportions with the worker problem. Is there anything else you'd like to add before we wrap up?",
    timestamp: new Date(Date.now() - 60000).toISOString(),
  },
];

const AssessmentPage: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { state, actions } = useAssessmentState();
  const api = useAssessmentApi();

  // Check for mock mode
  const isMockClosure = searchParams.get('mockClosure') === 'true';
  const mockInitializedRef = useRef(false);

  // Set up mock state if in mock mode - runs once before normal init
  useEffect(() => {
    if (isMockClosure && !mockInitializedRef.current) {
      mockInitializedRef.current = true;
      actions.setMockState({
        phase: 'closure_ready',
        attemptId: 'mock-attempt-id',
        assignmentId: assignmentId || 'mock-assignment',
        objectiveTitle: 'Ratios and Proportional Reasoning (Mock)',
        messages: MOCK_MESSAGES,
        isWaitingForResponse: false,
        error: null,
        startedAt: new Date(Date.now() - 300000).toISOString(),
      });
    }
  }, [isMockClosure, assignmentId, actions]);

  // Recording session for video/audio capture
  const {
    sessionState,
    stream,
    duration,
    isPausedByVisibility,
    initialize: initializeRecording,
    startRecording,
    stopRecording,
    abandon: abandonRecording,
  } = useRecordingSession({
    pauseOnHidden: true,
    autoStart: false,
  });

  // Navigation guard - block navigation when assessment is active
  const shouldBlockNavigation =
    state.phase === 'in_progress' || sessionState === 'recording';
  const {
    isBlocked: isNavigationBlocked,
    proceed: proceedNavigation,
    cancel: cancelNavigation,
  } = useNavigationGuard({
    shouldBlock: shouldBlockNavigation,
    message: 'Your recording will be stopped if you leave this page.',
  });

  // Keep refs to cleanup functions for unmount
  const abandonRef = useRef(abandonRecording);
  abandonRef.current = abandonRecording;
  const cancelStreamRef = useRef(api.cancelStream);
  cancelStreamRef.current = api.cancelStream;

  // Cleanup recording session and API streams on unmount (e.g., navigation away)
  useEffect(() => {
    return () => {
      abandonRef.current();
      cancelStreamRef.current();
    };
  }, []);

  // Completion state
  const [completionStep, setCompletionStep] = useState<CompletionStep | null>(
    null
  );
  const [completionError, setCompletionError] = useState<string | null>(null);
  const [completedAt, setCompletedAt] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const completionStartTimeRef = useRef<number | null>(null);

  // Minimum time to show completion screen before transitioning to complete
  const COMPLETION_MIN_DISPLAY_MS = 3000;

  // Track streamed content for the current message
  const streamedContentRef = useRef('');

  // Track if user has confirmed ready to start
  const [isStartingAssessment, setIsStartingAssessment] = useState(false);

  // Track if completion is pending (waiting for final message speech to start)
  const completionPendingRef = useRef(false);

  // Initialize assessment state when component mounts (skip in mock mode)
  useEffect(() => {
    if (isMockClosure) return; // Skip normal init in mock mode
    if (assignmentId && state.phase === 'idle') {
      actions.initialize(assignmentId);
    }
  }, [assignmentId, state.phase, actions, isMockClosure]);

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

    // Track when completion screen first appears
    completionStartTimeRef.current = Date.now();
    setUploadProgress(0);
    setCompletionStep('stopping');
    setCompletionError(null);
    actions.beginCompletion();

    try {
      // Step 1: Stop recording and get the video blob
      const videoBlob = await stopRecording();

      // Step 2: Upload video if we have a blob
      if (videoBlob) {
        setCompletionStep('uploading');
        const uploadResponse = await uploadAssessmentVideo({
          path: { attempt_id: state.attemptId },
          body: { video: videoBlob },
        });
        setUploadProgress(100);
        if (uploadResponse.error) {
          console.warn('Video upload failed:', uploadResponse.error);
          // Continue with completion even if video upload fails
        }
      }

      // Step 3: Complete assessment via API
      setCompletionStep('completing');
      const response = await completeAssessmentApi({
        path: { attempt_id: state.attemptId },
        body: { feedback: null },
      });

      if (response.error) {
        throw new Error('Failed to complete assessment');
      }

      // Ensure minimum display time before showing complete
      const elapsed = Date.now() - (completionStartTimeRef.current || 0);
      const remainingTime = COMPLETION_MIN_DISPLAY_MS - elapsed;
      if (remainingTime > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingTime));
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
  }, [state.attemptId, actions, stopRecording]);

  // Handle AI-triggered completion - defer showing banner until speech starts
  const handleAICompletion = useCallback(() => {
    if (!state.attemptId || state.phase !== 'in_progress') {
      return;
    }
    // Mark completion as pending - will show banner when speech starts
    completionPendingRef.current = true;
  }, [state.attemptId, state.phase]);

  // Handle turn changes from VoiceConversationLoop
  const handleTurnChange = useCallback(
    (turn: ConversationTurn) => {
      // When speech starts playing and completion is pending, show the banner
      if (turn === 'ai_speaking' && completionPendingRef.current) {
        completionPendingRef.current = false;
        actions.closureReady();
      }
    },
    [actions]
  );

  // Handle learner choosing to finish from closure_ready state
  const handleFinishAssessment = useCallback(async () => {
    if (state.phase !== 'closure_ready' || !state.attemptId) return;

    // Track when completion screen first appears
    completionStartTimeRef.current = Date.now();
    setUploadProgress(0);
    setCompletionStep('stopping');
    actions.beginCompletion();

    try {
      // Stop recording and get the video blob
      const videoBlob = await stopRecording();

      // Upload video if we have a blob
      if (videoBlob) {
        setCompletionStep('uploading');
        const uploadResponse = await uploadAssessmentVideo({
          path: { attempt_id: state.attemptId },
          body: { video: videoBlob },
        });
        setUploadProgress(100);
        if (uploadResponse.error) {
          console.warn('Video upload failed:', uploadResponse.error);
          // Continue with completion even if video upload fails
        }
      }

      // Show completing step (backend already marked complete, but show for UX)
      setCompletionStep('completing');

      // Ensure minimum display time before showing complete
      const elapsed = Date.now() - (completionStartTimeRef.current || 0);
      const remainingTime = COMPLETION_MIN_DISPLAY_MS - elapsed;
      if (remainingTime > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingTime));
      }

      // Done!
      setCompletedAt(new Date().toISOString());
      setCompletionStep('complete');
      actions.completeAssessment();
    } catch (error) {
      console.error('Error during finish assessment:', error);
      // Still complete even if recording/upload fails
      setCompletedAt(new Date().toISOString());
      setCompletionStep('complete');
      actions.completeAssessment();
    }
  }, [state.phase, state.attemptId, actions, stopRecording]);

  // Set up completion callback when API signals assessment is done
  useEffect(() => {
    api.onComplete(() => {
      // AI has determined the assessment is complete
      handleAICompletion();
    });

    return () => {
      api.onComplete(null);
    };
  }, [api, handleAICompletion]);

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
        uploadProgress={uploadProgress}
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
                className="w-full px-6 py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-colors flex flex-col items-center justify-center"
              >
                {isStartingAssessment ? (
                  <>
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                      <span className="text-lg font-medium">Starting...</span>
                    </div>
                    <span className="text-sm text-blue-200 mt-1">
                      Please wait
                    </span>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <svg
                        className="w-5 h-5"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="text-lg font-medium">I'm Ready</span>
                    </div>
                    <span className="text-sm text-blue-200 mt-1">
                      Begin Assessment
                    </span>
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

  // Render active assessment (in_progress, closure_ready, or completing)
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">
            {state.objectiveTitle || 'Assessment'}
          </h1>
          <p className="text-sm text-gray-500">
            {state.phase === 'closure_ready'
              ? 'Interview concluded'
              : 'Assessment in progress'}
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
            isRecording={isMockClosure || sessionState === 'recording'}
            isPaused={!isMockClosure && sessionState === 'paused'}
            durationSeconds={isMockClosure ? 127 : duration}
            isPausedByVisibility={!isMockClosure && isPausedByVisibility}
            stream={stream}
            showAudioLevel={!isMockClosure}
          />

          {/* Complete button - only show when not in closure_ready (banner handles it) */}
          {state.phase !== 'closure_ready' && (
            <button
              onClick={handleCompleteAssessment}
              disabled={
                state.isWaitingForResponse || state.phase === 'completing'
              }
              className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Complete Assessment
            </button>
          )}
        </div>
      </header>

      {/* Voice conversation interface */}
      <div className="flex-1 overflow-hidden">
        <VoiceConversationLoop
          messages={state.messages}
          onSendMessage={handleSendMessage}
          isWaitingForResponse={state.isWaitingForResponse}
          isAssessmentComplete={state.phase === 'completing'}
          autoPlayResponses={!isMockClosure}
          voice="nova"
          speechSpeed={1.1}
          onTurnChange={handleTurnChange}
          inputHeaderContent={
            state.phase === 'closure_ready' ? (
              <div className="bg-blue-50 border-b border-blue-200 px-6 py-4">
                <div className="max-w-3xl mx-auto space-y-3">
                  <div>
                    <p className="text-sm font-medium text-blue-800">
                      The interviewer has concluded the assessment.
                    </p>
                    <p className="text-sm text-blue-600">
                      You can add more thoughts or complete when ready.
                    </p>
                  </div>
                  {/* Actions row */}
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => actions.continueAssessment()}
                      className="px-4 py-2 text-sm font-medium text-blue-700 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors"
                    >
                      Add Response
                    </button>
                    <button
                      onClick={handleFinishAssessment}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
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
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      Complete Assessment
                    </button>
                  </div>
                </div>
              </div>
            ) : undefined
          }
        />
      </div>

      {/* Camera preview (minimizable) */}
      <CameraPreview
        stream={stream}
        isRecording={isMockClosure || sessionState === 'recording'}
        hasAudio
        position="bottom-right"
        defaultMinimized={false}
        showPlaceholder={isMockClosure}
      />

      {/* Tab visibility warning overlay */}
      <TabVisibilityWarning isVisible={isPausedByVisibility} />

      {/* Navigation confirmation dialog */}
      <NavigationConfirmDialog
        isOpen={isNavigationBlocked}
        onConfirm={proceedNavigation}
        onCancel={cancelNavigation}
      />
    </div>
  );
};

export default AssessmentPage;
