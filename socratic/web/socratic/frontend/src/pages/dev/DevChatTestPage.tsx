import React, { useEffect } from 'react';
import {
  ChatInterface,
  ChatMessage,
  useAssessmentState,
  type AssessmentPhase,
} from '../../components/assessment';

const phaseColors: Record<AssessmentPhase, string> = {
  idle: 'bg-gray-400',
  initializing: 'bg-yellow-400',
  ready: 'bg-blue-400',
  in_progress: 'bg-green-400',
  completing: 'bg-purple-400',
  completed: 'bg-green-600',
  error: 'bg-red-500',
};

/**
 * Development test page for chat components and assessment state machine.
 */
const DevChatTestPage: React.FC = () => {
  const { state, actions } = useAssessmentState();

  // Initialize with a fake assignment on mount
  useEffect(() => {
    if (state.phase === 'idle') {
      actions.initialize('test-assignment-123');
    }
  }, [state.phase, actions]);

  const demoStreaming = () => {
    const streamText =
      'This message is being streamed token by token, simulating how the AI response will appear in real-time during an assessment.';
    const tokens = streamText.split(' ');

    // Add empty streaming message using the hook action
    const msgId = actions.addInterviewerMessage('', true);
    actions.responseStarted();

    // Stream tokens one at a time
    let currentContent = '';
    tokens.forEach((token, i) => {
      setTimeout(() => {
        currentContent += (i === 0 ? '' : ' ') + token;
        actions.updateStreamingMessage(msgId, currentContent);

        // Finish streaming on last token
        if (i === tokens.length - 1) {
          setTimeout(() => {
            actions.finishStreamingMessage(msgId);
            actions.responseComplete();
          }, 200);
        }
      }, i * 100);
    });
  };

  const handleSendMessage = (content: string) => {
    // Use the hook's sendMessage action (adds learner message + sets waiting)
    actions.sendMessage(content);

    // Simulate AI response after delay with streaming
    setTimeout(() => {
      const responseText = `Thanks for sharing about "${content.slice(0, 20)}...". That's an interesting perspective. Can you elaborate on that point?`;
      const tokens = responseText.split(' ');

      const msgId = actions.addInterviewerMessage('', true);

      let currentContent = '';
      tokens.forEach((token, i) => {
        setTimeout(() => {
          currentContent += (i === 0 ? '' : ' ') + token;
          actions.updateStreamingMessage(msgId, currentContent);

          if (i === tokens.length - 1) {
            setTimeout(() => {
              actions.finishStreamingMessage(msgId);
              actions.responseComplete();
            }, 100);
          }
        }, i * 50);
      });
    }, 500);
  };

  const handlePhaseTransition = (targetPhase: AssessmentPhase) => {
    switch (targetPhase) {
      case 'idle':
        actions.reset();
        break;
      case 'initializing':
        actions.initialize('test-assignment-123');
        break;
      case 'ready':
        actions.grantPermissions();
        break;
      case 'in_progress':
        actions.startAssessment(
          'test-attempt-456',
          'Understanding React Hooks'
        );
        actions.addInterviewerMessage(
          "Hello! I'm here to assess your understanding of React hooks. Let's begin with a question: Can you explain what useEffect does?"
        );
        actions.responseComplete();
        break;
      case 'completing':
        actions.beginCompletion();
        break;
      case 'completed':
        actions.completeAssessment();
        break;
      case 'error':
        actions.setError('Simulated error for testing');
        break;
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-semibold">Assessment State Machine Test</h1>
        <p className="text-sm text-gray-500">
          Testing useAssessmentState hook and chat components
        </p>
      </header>

      {/* State display */}
      <div className="bg-gray-50 px-6 py-3 border-b">
        <div className="flex items-center gap-4 mb-2">
          <span className="text-sm font-medium">Current Phase:</span>
          <span
            className={`px-3 py-1 rounded-full text-white text-sm font-medium ${phaseColors[state.phase]}`}
          >
            {state.phase}
          </span>
          <span className="text-sm text-gray-500">
            | Messages: {state.messages.length} | Waiting:{' '}
            {state.isWaitingForResponse ? 'Yes' : 'No'}
          </span>
        </div>
        {state.error && (
          <div className="text-red-600 text-sm mb-2">Error: {state.error}</div>
        )}
        {state.objectiveTitle && (
          <div className="text-sm text-gray-600">
            Objective: {state.objectiveTitle}
          </div>
        )}
      </div>

      {/* Phase transition controls */}
      <div className="bg-gray-100 px-6 py-3 border-b flex flex-wrap gap-2 items-center">
        <span className="text-sm font-medium mr-2">Transitions:</span>
        {(
          [
            'idle',
            'initializing',
            'ready',
            'in_progress',
            'completing',
            'completed',
            'error',
          ] as AssessmentPhase[]
        ).map((phase) => (
          <button
            key={phase}
            onClick={() => handlePhaseTransition(phase)}
            className={`text-xs px-2 py-1 rounded ${
              state.phase === phase
                ? 'bg-gray-800 text-white'
                : 'bg-white border hover:bg-gray-50'
            }`}
          >
            {phase}
          </button>
        ))}
        <div className="border-l pl-4 ml-2">
          <button
            onClick={demoStreaming}
            disabled={
              state.isWaitingForResponse || state.phase !== 'in_progress'
            }
            className="text-sm px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
          >
            Demo Streaming
          </button>
        </div>
      </div>

      {/* Individual message examples */}
      <div className="bg-white px-6 py-4 border-b">
        <h2 className="text-sm font-medium text-gray-700 mb-3">
          Individual ChatMessage Examples:
        </h2>
        <div className="max-w-2xl">
          <ChatMessage
            message={{
              id: 'demo-1',
              type: 'interviewer',
              content: 'Interviewer message (left aligned)',
            }}
          />
          <ChatMessage
            message={{
              id: 'demo-2',
              type: 'learner',
              content: 'Learner message (right aligned, blue)',
            }}
          />
          <ChatMessage
            message={{
              id: 'demo-3',
              type: 'system',
              content: 'System message (centered)',
            }}
          />
          <ChatMessage
            message={{
              id: 'demo-4',
              type: 'interviewer',
              content: 'Streaming message with cursor',
              isStreaming: true,
            }}
          />
        </div>
      </div>

      {/* Full ChatInterface using state machine */}
      <div className="flex-1 overflow-hidden">
        <ChatInterface
          messages={state.messages}
          onSendMessage={handleSendMessage}
          isWaitingForResponse={state.isWaitingForResponse}
          isAssessmentComplete={state.phase === 'completed'}
          disabled={state.phase !== 'in_progress'}
        />
      </div>
    </div>
  );
};

export default DevChatTestPage;
