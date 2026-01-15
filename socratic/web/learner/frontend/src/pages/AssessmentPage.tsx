import React, { useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ChatInterface, useAssessmentState } from '../components/assessment';

/**
 * Mock service for development.
 * TODO: Replace with real API integration when backend is ready.
 */
const mockService = {
  // Simulated prompts for the assessment
  prompts: [
    "Hello! I'm here to help assess your understanding of this topic. Let's start with a foundational question: Can you explain the main concept in your own words?",
    "That's interesting. Can you give me a specific example of how this applies in practice?",
    'Good. Now, what are some potential challenges or limitations you might encounter?',
    "Let's dig a bit deeper. How would you handle a situation where the typical approach doesn't work?",
    "Finally, how does this concept connect to other things you've learned? Can you see any relationships?",
  ],

  currentPromptIndex: 0,

  async startAssessment(_assignmentId: string): Promise<{
    attemptId: string;
    objectiveTitle: string;
    initialPrompt: string;
  }> {
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 1000));
    this.currentPromptIndex = 0;
    return {
      attemptId: `attempt-${Date.now()}`,
      objectiveTitle: 'Understanding Core Concepts',
      initialPrompt: this.prompts[0],
    };
  },

  async sendMessage(
    _attemptId: string,
    _content: string
  ): Promise<{ response: string; isComplete: boolean }> {
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    this.currentPromptIndex++;
    const isComplete = this.currentPromptIndex >= this.prompts.length;

    if (isComplete) {
      return {
        response:
          'Thank you for your thoughtful responses. I have a good understanding of your knowledge now. The assessment is complete. Your responses have been recorded and will be reviewed by your instructor.',
        isComplete: true,
      };
    }

    return {
      response: this.prompts[this.currentPromptIndex],
      isComplete: false,
    };
  },
};

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

      try {
        // For now, skip permissions and go straight to starting
        // TODO: Add permission request flow for a/v capture

        const result = await mockService.startAssessment(state.assignmentId);

        actions.startAssessment(result.attemptId, result.objectiveTitle);
        actions.addInterviewerMessage(result.initialPrompt);
        actions.responseComplete();
      } catch (err) {
        actions.setError('Failed to start assessment. Please try again.');
      }
    };

    startAssessmentFlow();
  }, [state.phase, state.assignmentId, actions]);

  // Handle sending messages
  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!state.attemptId) return;

      // Add learner message and mark as waiting
      actions.sendMessage(content);

      try {
        const result = await mockService.sendMessage(state.attemptId, content);

        // Add interviewer response
        actions.addInterviewerMessage(result.response);
        actions.responseComplete();

        // Check if assessment is complete
        if (result.isComplete) {
          actions.addSystemMessage(
            'Assessment complete. Submitting your responses...'
          );
          actions.beginCompletion();

          // Simulate submission delay
          await new Promise((resolve) => setTimeout(resolve, 1000));
          actions.completeAssessment();
        }
      } catch (err) {
        actions.setError('Failed to send message. Please try again.');
      }
    },
    [state.attemptId, actions]
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
