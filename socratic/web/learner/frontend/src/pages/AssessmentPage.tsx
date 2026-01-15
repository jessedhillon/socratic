import React, { useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ChatInterface,
  useAssessmentState,
  useAssessmentApi,
} from '../components/assessment';

/**
 * Assessment page - where learners complete their assessments.
 *
 * This page manages the full assessment flow:
 * 1. Initialize and load assignment
 * 2. Display orientation/consent
 * 3. Turn-based conversation with AI
 * 4. Completion and submission
 */
const AssessmentPage: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const { state, actions } = useAssessmentState();
  const api = useAssessmentApi();

  // Track if we've started initialization to prevent double-starts
  const initStartedRef = useRef(false);

  // Track streamed content for the current message
  const streamedContentRef = useRef('');

  // Initialize assessment when component mounts
  useEffect(() => {
    if (assignmentId && state.phase === 'idle') {
      actions.initialize(assignmentId);
    }
  }, [assignmentId, state.phase, actions]);

  // Start assessment when in initializing phase
  useEffect(() => {
    const startAssessmentFlow = async () => {
      if (state.phase !== 'initializing' || !state.assignmentId) return;

      // Prevent double-start due to React strict mode
      if (initStartedRef.current) return;
      initStartedRef.current = true;

      try {
        // Create a streaming message placeholder
        streamedContentRef.current = '';
        const messageId = actions.addInterviewerMessage('', true);

        const result = await api.startAssessment(
          state.assignmentId,
          (token) => {
            // Update streaming message with each token
            streamedContentRef.current += token;
            actions.updateStreamingMessage(
              messageId,
              streamedContentRef.current
            );
          }
        );

        // Finalize the message
        actions.finishStreamingMessage(messageId);
        actions.startAssessment(result.attemptId, result.objectiveTitle);
        actions.responseComplete();
      } catch (err) {
        console.error('Failed to start assessment:', err);
        actions.setError('Failed to start assessment. Please try again.');
        initStartedRef.current = false;
      }
    };

    startAssessmentFlow();
  }, [state.phase, state.assignmentId, actions, api]);

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

  // Render loading state
  if (state.phase === 'idle' || state.phase === 'initializing') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Preparing your assessment...</p>
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

  // Render completed state
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
          <ChatInterface
            messages={state.messages}
            onSendMessage={() => {}}
            isWaitingForResponse={false}
            isAssessmentComplete={true}
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

  // Render active assessment
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

        {/* Progress indicator placeholder */}
        <div className="text-sm text-gray-500">
          {state.messages.filter((m) => m.type === 'learner').length} responses
        </div>
      </header>

      {/* Chat interface */}
      <div className="flex-1 overflow-hidden">
        <ChatInterface
          messages={state.messages}
          onSendMessage={handleSendMessage}
          isWaitingForResponse={state.isWaitingForResponse}
          isAssessmentComplete={state.phase === 'completing'}
        />
      </div>
    </div>
  );
};

export default AssessmentPage;
