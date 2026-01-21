import React, { useEffect, useState, useCallback } from 'react';
import {
  ChatInterface,
  ChatMessage,
  useAssessmentState,
  type AssessmentPhase,
  type ChatMessageData,
} from '../../components/assessment';
import { useSpeech } from '../../hooks';

const phaseColors: Record<AssessmentPhase, string> = {
  idle: 'bg-gray-400',
  initializing: 'bg-yellow-400',
  ready: 'bg-blue-400',
  in_progress: 'bg-green-400',
  completing: 'bg-purple-400',
  completed: 'bg-green-600',
  error: 'bg-red-500',
};

/** Sample messages for TTS testing */
const TTS_TEST_MESSAGES = [
  "Hello! Let's begin the assessment. Can you tell me about your experience with React?",
  "That's interesting. How do you handle state management in complex applications?",
  'Good point. Can you explain the difference between useEffect and useLayoutEffect?',
  "Excellent explanation. Now, let's talk about performance optimization techniques.",
];

/**
 * Development test page for chat components and assessment state machine.
 */
const DevChatTestPage: React.FC = () => {
  const { state, actions } = useAssessmentState();
  const { state: speechState, speak, stop: stopSpeech } = useSpeech();

  // TTS + animated text demo state
  const [ttsMessages, setTtsMessages] = useState<ChatMessageData[]>([]);
  const [pendingMessageId, setPendingMessageId] = useState<string | null>(null);
  const [animatingMessageId, setAnimatingMessageId] = useState<string | null>(
    null
  );
  const [speechSpeed, setSpeechSpeed] = useState(1.1);
  const [ttsMessageIndex, setTtsMessageIndex] = useState(0);

  // When audio starts playing, move message from pending to animating
  useEffect(() => {
    if (speechState.isPlaying && pendingMessageId) {
      setAnimatingMessageId(pendingMessageId);
      setPendingMessageId(null);
    }
  }, [speechState.isPlaying, pendingMessageId]);

  const handleAnimationComplete = useCallback(() => {
    setAnimatingMessageId(null);
  }, []);

  const handleTtsDemo = useCallback(async () => {
    const text = TTS_TEST_MESSAGES[ttsMessageIndex % TTS_TEST_MESSAGES.length];
    const msgId = `tts-demo-${Date.now()}`;

    // Add message to list (hidden until audio plays)
    const newMessage: ChatMessageData = {
      id: msgId,
      type: 'interviewer',
      content: text,
    };
    setTtsMessages((prev) => [...prev, newMessage]);
    setPendingMessageId(msgId);

    // Cycle to next message for next demo
    setTtsMessageIndex((prev) => prev + 1);

    try {
      await speak(text, {
        voice: 'nova',
        speed: speechSpeed,
        autoPlay: true,
      });
    } catch (err) {
      console.error('TTS failed:', err);
      // Show message anyway on error
      setPendingMessageId(null);
    }
  }, [ttsMessageIndex, speak, speechSpeed]);

  const handleSkipSpeech = () => {
    stopSpeech();
    // Also skip the typewriter animation
    setAnimatingMessageId(null);
  };

  const handleClearTtsMessages = () => {
    stopSpeech();
    setTtsMessages([]);
    setPendingMessageId(null);
    setAnimatingMessageId(null);
  };

  // Filter visible messages (hide pending)
  const visibleTtsMessages = ttsMessages.filter(
    (msg) => msg.id !== pendingMessageId
  );

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

      {/* TTS + Animated Text Demo */}
      <div className="bg-blue-50 px-6 py-4 border-b">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-gray-700">
            TTS + Synchronized Text Animation Test
          </h2>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-600">Speed:</label>
              <select
                value={speechSpeed}
                onChange={(e) => setSpeechSpeed(parseFloat(e.target.value))}
                className="text-xs border rounded px-2 py-1"
              >
                <option value={0.8}>0.8x</option>
                <option value={1}>1.0x</option>
                <option value={1.1}>1.1x</option>
                <option value={1.25}>1.25x</option>
                <option value={1.5}>1.5x</option>
              </select>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span
                className={`w-2 h-2 rounded-full ${
                  speechState.isLoading
                    ? 'bg-yellow-500'
                    : speechState.isPlaying
                      ? 'bg-green-500 animate-pulse'
                      : 'bg-gray-300'
                }`}
              />
              <span>
                {speechState.isLoading
                  ? 'Loading...'
                  : speechState.isPlaying
                    ? 'Playing'
                    : 'Idle'}
              </span>
              {pendingMessageId && (
                <span className="text-blue-600">(text hidden)</span>
              )}
              {animatingMessageId && (
                <span className="text-green-600">(animating)</span>
              )}
              {speechState.duration && (
                <span className="text-purple-600">
                  (duration: {speechState.duration.toFixed(2)}s)
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex gap-2 mb-3">
          <button
            onClick={handleTtsDemo}
            disabled={speechState.isLoading || speechState.isPlaying}
            className="text-sm px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            Play TTS Demo
          </button>
          <button
            onClick={stopSpeech}
            disabled={!speechState.isPlaying}
            className="text-sm px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            Stop
          </button>
          <button
            onClick={handleClearTtsMessages}
            className="text-sm px-4 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200"
          >
            Clear Messages
          </button>
        </div>

        {speechState.error && (
          <div className="text-sm text-red-600 mb-3">
            Error: {speechState.error}
          </div>
        )}

        <div className="max-w-2xl bg-white rounded-lg p-4 max-h-64 overflow-y-auto">
          {visibleTtsMessages.length === 0 ? (
            <div className="text-gray-400 text-sm text-center py-4">
              Click "Play TTS Demo" to test TTS with synchronized text animation
            </div>
          ) : (
            visibleTtsMessages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                isSpeaking={
                  speechState.isPlaying && msg.id === animatingMessageId
                }
                onSkipSpeech={handleSkipSpeech}
                animateReveal={msg.id === animatingMessageId}
                onAnimationComplete={handleAnimationComplete}
                audioDurationSeconds={
                  msg.id === animatingMessageId ? speechState.duration : null
                }
                speechSpeed={speechSpeed}
              />
            ))
          )}
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
