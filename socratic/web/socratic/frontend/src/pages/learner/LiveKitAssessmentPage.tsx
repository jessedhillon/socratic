/**
 * LiveKit-based real-time voice assessment page.
 *
 * This page handles the full assessment flow using LiveKit for real-time voice:
 * 1. Request permissions (camera/microphone)
 * 2. Show camera preview and confirm ready
 * 3. Start assessment and connect to LiveKit room
 * 4. Real-time voice conversation with AI agent
 * 5. Completion with summary and confirmation
 */
import React, {
  useEffect,
  useCallback,
  useRef,
  useState,
  useMemo,
} from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  LiveKitVoiceConversation,
  AssessmentCompletionScreen,
  type CompletionStep,
  type AssessmentSummary,
  type ChatMessageData,
} from '../../components/assessment';
import { RecordingStatusOverlay } from '../../components/RecordingStatusOverlay';
import { PermissionGate } from '../../components/PermissionGate';
import { CameraPreview } from '../../components/CameraPreview';
import { TabVisibilityWarning } from '../../components/TabVisibilityWarning';
import { NavigationConfirmDialog } from '../../components/NavigationConfirmDialog';
import { useRecordingSession } from '../../hooks/useRecordingSession';
import { useNavigationGuard } from '../../hooks/useNavigationGuard';
import {
  startLiveKitAssessment,
  type StartLiveKitAssessmentResponse,
} from '../../api/livekit';
import { type LiveKitConnectionState } from '../../hooks/useLiveKitRoom';
import { completeAssessment as completeAssessmentApi } from '../../api/sdk.gen';

type AssessmentPhase =
  | 'idle'
  | 'initializing'
  | 'ready'
  | 'connecting'
  | 'in_progress'
  | 'closure_ready'
  | 'completing'
  | 'completed'
  | 'error';

interface AssessmentState {
  phase: AssessmentPhase;
  error: string | null;
  attemptId: string | null;
  assignmentId: string | null;
  objectiveId: string | null;
  objectiveTitle: string | null;
  roomName: string | null;
  token: string | null;
  serverUrl: string | null;
  startedAt: string | null;
  messages: ChatMessageData[];
}

const initialState: AssessmentState = {
  phase: 'idle',
  error: null,
  attemptId: null,
  assignmentId: null,
  objectiveId: null,
  objectiveTitle: null,
  roomName: null,
  token: null,
  serverUrl: null,
  startedAt: null,
  messages: [],
};

const LiveKitAssessmentPage: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<AssessmentState>(initialState);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [isStartingAssessment, setIsStartingAssessment] = useState(false);

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

  // Track if user is leaving the page (confirmed navigation)
  const [isLeavingPage, setIsLeavingPage] = useState(false);

  // Deferred completion: the agent signalled completion but the farewell
  // message may still be streaming.  We wait for it to finish before
  // transitioning to closure_ready (which disconnects the room).
  const [pendingCompletion, setPendingCompletion] = useState(false);

  // Recording session for video capture (local recording, not LiveKit Egress)
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
    chunkUploadIntervalMs: 10000,
    externalStream: mediaStream,
  });

  // Navigation guard - block navigation when assessment is active
  const shouldBlockNavigation =
    state.phase === 'in_progress' ||
    state.phase === 'connecting' ||
    sessionState === 'recording';
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
  const mediaStreamRef = useRef(mediaStream);
  mediaStreamRef.current = mediaStream;

  // Cleanup on unmount — stop all media tracks and abandon recording
  useEffect(() => {
    return () => {
      abandonRef.current();
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  // Initialize when component mounts
  useEffect(() => {
    if (assignmentId && state.phase === 'idle') {
      setState((prev) => ({
        ...prev,
        phase: 'initializing',
        assignmentId,
      }));
    }
  }, [assignmentId, state.phase]);

  // Handle permission granted - acquire stream and initialize recording
  const handlePermissionsGranted = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      setMediaStream(stream);

      // Initialize recording with the stream
      await initializeRecording();

      setState((prev) => ({
        ...prev,
        phase: 'ready',
      }));
    } catch (err) {
      console.error('Failed to initialize media:', err);
      setState((prev) => ({
        ...prev,
        phase: 'error',
        error: 'Failed to access camera and microphone. Please try again.',
      }));
    }
  }, [initializeRecording]);

  // Handle "I'm Ready" button click - start assessment
  const handleStartAssessment = useCallback(async () => {
    if (!state.assignmentId || isStartingAssessment) return;

    setIsStartingAssessment(true);

    try {
      // Start local recording first
      await startRecording();

      setState((prev) => ({
        ...prev,
        phase: 'connecting',
      }));

      // Call the backend to create attempt and get LiveKit credentials
      const result: StartLiveKitAssessmentResponse =
        await startLiveKitAssessment(state.assignmentId);

      setState((prev) => ({
        ...prev,
        phase: 'in_progress',
        attemptId: result.attempt_id,
        objectiveId: result.objective_id,
        objectiveTitle: result.objective_title,
        roomName: result.room_name,
        token: result.token,
        serverUrl: result.url,
        startedAt: new Date().toISOString(),
      }));
    } catch (err) {
      console.error('Failed to start assessment:', err);
      setState((prev) => ({
        ...prev,
        phase: 'error',
        error:
          err instanceof Error
            ? err.message
            : 'Failed to start assessment. Please try again.',
      }));
    } finally {
      setIsStartingAssessment(false);
    }
  }, [state.assignmentId, isStartingAssessment, startRecording]);

  // Track which segments belong to which message, and per-segment text,
  // so we can coalesce consecutive same-speaker segments into one bubble
  // while still handling interim segment updates correctly.
  const segmentToMessageRef = useRef<Map<string, string>>(new Map());
  const messageSegmentsRef = useRef<Map<string, Map<string, string>>>(
    new Map()
  );

  // Handle transcription segments from LiveKit
  const handleTranscription = useCallback(
    (
      segments: Array<{ id: string; text: string; isFinal: boolean }>,
      _participantIdentity: string,
      isLocal: boolean
    ) => {
      const utteranceType = isLocal ? 'learner' : 'interviewer';
      const segToMsg = segmentToMessageRef.current;
      const msgSegs = messageSegmentsRef.current;

      setState((prev) => {
        const updatedMessages = [...prev.messages];

        for (const segment of segments) {
          const existingMessageId = segToMsg.get(segment.id);

          // Guard: only treat as "existing" if the message is actually in
          // the array.  React StrictMode double-invokes setState updaters,
          // and the ref mutations from the first invocation would otherwise
          // trick the second invocation into looking for a message that
          // doesn't exist in prev.messages yet.
          const messageIdx =
            existingMessageId != null
              ? updatedMessages.findIndex((m) => m.id === existingMessageId)
              : -1;

          if (existingMessageId && messageIdx >= 0) {
            // Update an existing segment's text within its message
            const segs = msgSegs.get(existingMessageId);
            if (segs) {
              segs.set(segment.id, segment.text);
            }

            const allTexts = Array.from(segs?.values() ?? []);
            updatedMessages[messageIdx] = {
              ...updatedMessages[messageIdx],
              content: allTexts.join(' '),
              isStreaming: !segment.isFinal,
            };
          } else {
            // New segment — coalesce with last message if same speaker
            const lastMsg =
              updatedMessages.length > 0
                ? updatedMessages[updatedMessages.length - 1]
                : null;

            if (lastMsg && lastMsg.type === utteranceType) {
              // Append to existing message
              segToMsg.set(segment.id, lastMsg.id);
              let segs = msgSegs.get(lastMsg.id);
              if (!segs) {
                // Rebuild segment map from existing message content
                // (can happen after StrictMode double-invoke overwrites)
                segs = new Map();
                msgSegs.set(lastMsg.id, segs);
              }
              segs.set(segment.id, segment.text);

              const allTexts = Array.from(segs.values());
              updatedMessages[updatedMessages.length - 1] = {
                ...lastMsg,
                content: allTexts.join(' '),
                isStreaming: !segment.isFinal,
              };
            } else {
              // New speaker turn — create new message
              const messageId = segment.id;
              segToMsg.set(segment.id, messageId);
              msgSegs.set(messageId, new Map([[segment.id, segment.text]]));

              updatedMessages.push({
                id: messageId,
                type: utteranceType,
                content: segment.text,
                timestamp: new Date().toISOString(),
                isStreaming: !segment.isFinal,
              });
            }
          }
        }

        return { ...prev, messages: updatedMessages };
      });
    },
    []
  );

  // Handle LiveKit connection state changes
  const handleConnectionStateChange = useCallback(
    (connectionState: LiveKitConnectionState) => {
      if (connectionState === 'error') {
        setState((prev) => ({
          ...prev,
          phase: 'error',
          error: 'Lost connection to the assessment room.',
        }));
      }
    },
    []
  );

  // Handle data channel messages from the agent
  const handleDataReceived = useCallback(
    (data: Record<string, unknown>, _topic?: string) => {
      if (data.type === 'assessment.complete') {
        // Don't transition immediately — the agent's farewell message may
        // still be streaming.  Set a flag and let the effect below wait
        // for the last message to finish before disconnecting.
        setPendingCompletion(true);
      }
    },
    []
  );

  // Defer the closure_ready transition until the last message finishes
  // streaming, so the agent's farewell is fully played and displayed
  // before the room disconnects.
  useEffect(() => {
    if (!pendingCompletion || state.phase !== 'in_progress') return;

    const lastMsg =
      state.messages.length > 0
        ? state.messages[state.messages.length - 1]
        : null;
    const isStillStreaming = lastMsg?.isStreaming === true;

    if (!isStillStreaming) {
      setState((prev) => {
        if (prev.phase === 'in_progress') {
          return { ...prev, phase: 'closure_ready' };
        }
        return prev;
      });
      setPendingCompletion(false);
    }
  }, [pendingCompletion, state.phase, state.messages]);

  // Handle completing the assessment
  const handleCompleteAssessment = useCallback(async () => {
    if (!state.attemptId) return;

    // Track when completion screen first appears
    completionStartTimeRef.current = Date.now();
    setUploadProgress(0);
    setCompletionStep('stopping');
    setCompletionError(null);
    setState((prev) => ({
      ...prev,
      phase: 'completing',
    }));

    try {
      // Step 1: Stop recording
      await stopRecording();

      // Release camera/microphone tracks immediately so the hardware is freed.
      // The recording session may hold a different internal stream reference, so
      // we also explicitly stop the stream we acquired during permission setup.
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        setMediaStream(null);
      }

      // Step 2: Upload the video (if we have chunks to finalize)
      setCompletionStep('uploading');
      // TODO: Implement video chunk finalization for LiveKit mode
      setUploadProgress(100);

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
      setState((prev) => ({
        ...prev,
        phase: 'completed',
      }));
    } catch (err) {
      console.error('Failed to complete assessment:', err);
      setCompletionStep('error');
      setCompletionError(
        err instanceof Error
          ? err.message
          : 'An error occurred while completing your assessment.'
      );
    }
  }, [state.attemptId, stopRecording, mediaStream]);

  // Handle confirmed navigation away
  const handleConfirmLeave = useCallback(() => {
    // Stop media tracks so camera/mic are released before navigation
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      setMediaStream(null);
    }
    setIsLeavingPage(true);
    setTimeout(() => {
      proceedNavigation();
    }, 50);
  }, [proceedNavigation, mediaStream]);

  // Handle retry after error
  const handleRetryCompletion = useCallback(() => {
    setCompletionStep(null);
    setCompletionError(null);
  }, []);

  const handleClearError = useCallback(() => {
    setState((prev) => ({
      ...prev,
      phase: 'initializing',
      error: null,
    }));
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
              Voice Assessment Setup
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
              description="This voice assessment requires access to your camera and microphone. You'll be having a real-time conversation with an AI interviewer."
            >
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
              Ready to Begin Voice Assessment
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
                  Voice Assessment
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
                    Speak naturally - the AI will respond in real-time
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
                      <span className="text-lg font-medium">Connecting...</span>
                    </div>
                    <span className="text-sm text-blue-200 mt-1">
                      Setting up voice channel
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
                        <path d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8h-2a5 5 0 01-10 0H3a7.001 7.001 0 006 6.93V17H6v2h8v-2h-3v-2.07z" />
                      </svg>
                      <span className="text-lg font-medium">I'm Ready</span>
                    </div>
                    <span className="text-sm text-blue-200 mt-1">
                      Begin Voice Assessment
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
              onClick={handleClearError}
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

  // Render connecting state
  if (state.phase === 'connecting') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Connecting to voice channel...</p>
        </div>
      </div>
    );
  }

  // Render completed state
  if (state.phase === 'completed') {
    return (
      <div className="h-full flex flex-col">
        <header className="bg-white border-b px-6 py-4">
          <h1 className="text-xl font-semibold text-gray-800">
            {state.objectiveTitle || 'Assessment'}
          </h1>
          <p className="text-sm text-green-600">Assessment Complete</p>
        </header>

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-md">
            <div className="text-green-500 mb-4">
              <svg
                className="w-16 h-16 mx-auto"
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
            </div>
            <h2 className="text-xl font-semibold text-gray-800 mb-2">
              Assessment Submitted
            </h2>
            <p className="text-gray-600 mb-6">
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

  // Render active assessment (in_progress or closure_ready)
  if (
    (state.phase === 'in_progress' || state.phase === 'closure_ready') &&
    state.token &&
    state.serverUrl
  ) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-800">
              {state.objectiveTitle || 'Voice Assessment'}
            </h1>
            <p className="text-sm text-gray-500">
              {state.phase === 'closure_ready'
                ? 'Interview concluded'
                : 'Voice assessment in progress'}
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
              showAudioLevel={false}
            />

            {/* Complete button */}
            <button
              onClick={handleCompleteAssessment}
              className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Complete Assessment
            </button>
          </div>
        </header>

        {/* Voice conversation interface */}
        <div className="flex-1 overflow-hidden">
          <LiveKitVoiceConversation
            serverUrl={state.serverUrl}
            token={state.token}
            messages={state.messages}
            isAssessmentComplete={state.phase === 'closure_ready'}
            isLeavingPage={isLeavingPage}
            onConnectionStateChange={handleConnectionStateChange}
            onTranscription={handleTranscription}
            onDataReceived={handleDataReceived}
            inputHeaderContent={
              state.phase === 'closure_ready' ? (
                <div className="bg-blue-50 border-b border-blue-200 px-6 py-4">
                  <div className="max-w-3xl mx-auto space-y-3">
                    <div>
                      <p className="text-sm font-medium text-blue-800">
                        The interviewer has concluded the assessment.
                      </p>
                      <p className="text-sm text-blue-600">
                        You can continue speaking or complete when ready.
                      </p>
                    </div>
                    <button
                      onClick={handleCompleteAssessment}
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
              ) : undefined
            }
          />
        </div>

        {/* Camera preview */}
        <CameraPreview
          stream={stream}
          isRecording={sessionState === 'recording'}
          hasAudio
          position="bottom-right"
          defaultMinimized={false}
          showAudioLevel
        />

        {/* Tab visibility warning overlay */}
        <TabVisibilityWarning isVisible={isPausedByVisibility} />

        {/* Navigation confirmation dialog */}
        <NavigationConfirmDialog
          isOpen={isNavigationBlocked}
          onConfirm={handleConfirmLeave}
          onCancel={cancelNavigation}
        />
      </div>
    );
  }

  // Fallback - should not reach here
  return (
    <div className="h-full flex items-center justify-center">
      <p className="text-gray-600">Something went wrong. Please try again.</p>
    </div>
  );
};

export default LiveKitAssessmentPage;
