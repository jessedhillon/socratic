/**
 * Voice-based conversation loop component.
 *
 * Integrates voice input and TTS output for a hands-free assessment experience.
 * Manages turn-taking between the learner and AI interviewer.
 */

import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
} from 'react';
import ChatMessage, { type ChatMessageData } from './ChatMessage';
import VoiceInput from './VoiceInput';
import { useSpeech, type Voice } from '../../hooks';

/** Turn state for the conversation */
export type ConversationTurn =
  | 'learner'
  | 'ai_thinking'
  | 'ai_speaking'
  | 'idle';

export interface VoiceConversationLoopProps {
  /** Chat messages to display */
  messages: ChatMessageData[];
  /** Callback when the learner sends a message */
  onSendMessage: (content: string) => void;
  /** Whether waiting for AI response */
  isWaitingForResponse: boolean;
  /** Whether the assessment is complete */
  isAssessmentComplete: boolean;
  /** Whether the user is leaving the page (stops speech) */
  isLeavingPage?: boolean;
  /** Whether input is disabled */
  disabled?: boolean;
  /** Whether to auto-play AI responses */
  autoPlayResponses?: boolean;
  /** Voice to use for TTS */
  voice?: Voice;
  /** Speech speed (0.25-4.0) */
  speechSpeed?: number;
  /** Callback when turn changes */
  onTurnChange?: (turn: ConversationTurn) => void;
  /** Content to render above the input area (e.g., closure banner) */
  inputHeaderContent?: React.ReactNode;
}

/**
 * Voice-based conversation loop for assessments.
 *
 * Features:
 * - Voice input for learner responses (record → transcribe → review → send)
 * - Auto-play AI responses via TTS (text hidden until audio plays)
 * - Turn management (disables input while AI speaks)
 * - Skip button inside AI message bubbles when speaking
 * - Visual indicators for current turn state
 * - Fallback to text input if voice is unavailable
 *
 * @example
 * ```tsx
 * <VoiceConversationLoop
 *   messages={messages}
 *   onSendMessage={handleSendMessage}
 *   isWaitingForResponse={isWaiting}
 *   isAssessmentComplete={isComplete}
 *   autoPlayResponses
 *   voice="nova"
 * />
 * ```
 */
const VoiceConversationLoop: React.FC<VoiceConversationLoopProps> = ({
  messages,
  onSendMessage,
  isWaitingForResponse,
  isAssessmentComplete,
  isLeavingPage = false,
  disabled = false,
  autoPlayResponses = true,
  voice = 'nova',
  speechSpeed = 1.1,
  onTurnChange,
  inputHeaderContent,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastSpokenMessageId = useRef<string | null>(null);
  const [currentTurn, setCurrentTurn] = useState<ConversationTurn>('idle');
  // Track message ID that's waiting for audio to start playing
  const [pendingAudioMessageId, setPendingAudioMessageId] = useState<
    string | null
  >(null);
  // Track message ID that should animate with typewriter effect
  const [animatingMessageId, setAnimatingMessageId] = useState<string | null>(
    null
  );

  const { state: speechState, speak, stop: stopSpeech } = useSpeech();

  // When audio starts playing AND we have the duration, move message from pending to animating
  useEffect(() => {
    if (
      speechState.isPlaying &&
      pendingAudioMessageId &&
      speechState.duration &&
      speechState.duration > 0
    ) {
      setAnimatingMessageId(pendingAudioMessageId);
      setPendingAudioMessageId(null);
    }
  }, [speechState.isPlaying, pendingAudioMessageId, speechState.duration]);

  // Clear animation when audio stops
  useEffect(() => {
    if (!speechState.isPlaying && animatingMessageId) {
      // Keep animating until the typewriter finishes (handled by onAnimationComplete)
    }
  }, [speechState.isPlaying, animatingMessageId]);

  const handleAnimationComplete = useCallback(() => {
    setAnimatingMessageId(null);
  }, []);

  // Update turn state based on various conditions
  useEffect(() => {
    let newTurn: ConversationTurn;

    if (isAssessmentComplete) {
      newTurn = 'idle';
    } else if (speechState.isPlaying) {
      newTurn = 'ai_speaking';
    } else if (
      isWaitingForResponse ||
      speechState.isLoading ||
      pendingAudioMessageId
    ) {
      // Include audio loading in "thinking" state
      newTurn = 'ai_thinking';
    } else {
      newTurn = 'learner';
    }

    if (newTurn !== currentTurn) {
      setCurrentTurn(newTurn);
      onTurnChange?.(newTurn);
    }
  }, [
    isAssessmentComplete,
    speechState.isPlaying,
    speechState.isLoading,
    isWaitingForResponse,
    pendingAudioMessageId,
    currentTurn,
    onTurnChange,
  ]);

  // Stop speech when assessment completes or user is leaving page
  useEffect(() => {
    if (isAssessmentComplete || isLeavingPage) {
      stopSpeech();
    }
  }, [isAssessmentComplete, isLeavingPage, stopSpeech]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-play AI responses
  useEffect(() => {
    if (!autoPlayResponses || isAssessmentComplete) return;

    // Find the latest complete interviewer message
    const latestInterviewerMessage = [...messages]
      .reverse()
      .find(
        (msg) =>
          msg.type === 'interviewer' &&
          !msg.isStreaming &&
          msg.content.trim().length > 0
      );

    if (
      latestInterviewerMessage &&
      latestInterviewerMessage.id !== lastSpokenMessageId.current &&
      !speechState.isLoading &&
      !speechState.isPlaying
    ) {
      lastSpokenMessageId.current = latestInterviewerMessage.id;
      // Hide the message until audio starts playing
      setPendingAudioMessageId(latestInterviewerMessage.id);
      speak(latestInterviewerMessage.content, {
        voice,
        speed: speechSpeed,
        autoPlay: true,
      }).catch((err) => {
        console.error('Failed to speak AI response:', err);
        // Show the message on error so user can still read it
        setPendingAudioMessageId(null);
      });
    }
  }, [
    messages,
    autoPlayResponses,
    isAssessmentComplete,
    speechState.isLoading,
    speechState.isPlaying,
    speak,
    voice,
    speechSpeed,
  ]);

  // Filter out messages that shouldn't be visible yet (streaming or pending audio)
  const visibleMessages = useMemo(() => {
    return messages.filter((msg) => {
      // Always show learner and system messages
      if (msg.type !== 'interviewer') return true;
      // Hide streaming interviewer messages
      if (msg.isStreaming) return false;
      // Hide messages waiting for audio to start playing
      if (msg.id === pendingAudioMessageId) return false;
      return true;
    });
  }, [messages, pendingAudioMessageId]);

  // Check if we should show the "loading audio" indicator
  const isLoadingAudio =
    pendingAudioMessageId !== null ||
    messages.some((msg) => msg.type === 'interviewer' && msg.isStreaming);

  const handleVoiceSubmit = useCallback(
    (text: string) => {
      if (!disabled && !isAssessmentComplete) {
        onSendMessage(text);
      }
    },
    [disabled, isAssessmentComplete, onSendMessage]
  );

  const handleSkipSpeech = () => {
    stopSpeech();
    // Also skip the typewriter animation by clearing the animating state
    setAnimatingMessageId(null);
  };

  // AI's turn: waiting for response, loading audio, playing audio, or audio pending
  const isAiTurn =
    isWaitingForResponse ||
    speechState.isLoading ||
    speechState.isPlaying ||
    pendingAudioMessageId !== null;

  const isInputDisabled = disabled || isAssessmentComplete || isAiTurn;

  // Determine turn indicator content
  const getTurnIndicator = (): { text: string; className: string } => {
    switch (currentTurn) {
      case 'ai_speaking':
        return {
          text: 'AI is speaking...',
          className: 'bg-blue-100 text-blue-700',
        };
      case 'ai_thinking':
        return {
          text: 'AI is thinking...',
          className: 'bg-yellow-100 text-yellow-700',
        };
      case 'learner':
        return {
          text: 'Your turn to respond',
          className: 'bg-green-100 text-green-700',
        };
      default:
        return {
          text: '',
          className: '',
        };
    }
  };

  const turnIndicator = getTurnIndicator();

  return (
    <div className="flex flex-col h-full">
      {/* Turn indicator bar */}
      {!isAssessmentComplete && turnIndicator.text && (
        <div
          className={`flex items-center justify-between px-4 py-2 ${turnIndicator.className}`}
        >
          <div className="flex items-center gap-2">
            {currentTurn === 'ai_thinking' && (
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {currentTurn === 'ai_speaking' && (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <path
                  d="M15.54 8.46a5 5 0 0 1 0 7.07"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                />
              </svg>
            )}
            {currentTurn === 'learner' && (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
              </svg>
            )}
            <span className="text-sm font-medium">{turnIndicator.text}</span>
          </div>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 bg-gray-50">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 && !isWaitingForResponse && (
            <div className="text-center text-gray-500 py-8">
              The assessment will begin shortly...
            </div>
          )}

          {visibleMessages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              isSpeaking={
                speechState.isPlaying &&
                message.id === lastSpokenMessageId.current
              }
              onSkipSpeech={handleSkipSpeech}
              animateReveal={message.id === animatingMessageId}
              onAnimationComplete={handleAnimationComplete}
              audioDurationSeconds={
                message.id === animatingMessageId ? speechState.duration : null
              }
              speechSpeed={speechSpeed}
            />
          ))}

          {/* Audio loading indicator - shown while preparing TTS */}
          {isLoadingAudio && (
            <div className="flex justify-start mb-4">
              <div className="bg-white text-gray-800 shadow-sm border border-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
                <div className="text-xs text-gray-500 mb-1 font-medium">
                  Interviewer
                </div>
                <div className="flex items-center gap-2 text-gray-500">
                  <svg
                    className="w-4 h-4 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  <span className="text-sm">Preparing response...</span>
                </div>
              </div>
            </div>
          )}

          {/* Typing indicator */}
          {currentTurn === 'ai_thinking' && !isLoadingAudio && (
            <div className="flex justify-start mb-4">
              <div className="bg-white text-gray-800 shadow-sm border border-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
                <div className="flex items-center gap-1">
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="border-t bg-white">
        {/* Optional header content (e.g., closure banner) */}
        {inputHeaderContent}

        <div className="px-4 py-4">
          <div className="max-w-3xl mx-auto">
            {isAssessmentComplete ? (
              <div className="text-center text-gray-500 py-2">
                Assessment complete. Your responses have been submitted.
              </div>
            ) : (
              <div className="space-y-3">
                {/* Voice input */}
                <VoiceInput
                  onSubmit={handleVoiceSubmit}
                  disabled={isInputDisabled}
                />

                {/* Speech error display */}
                {speechState.error && (
                  <div className="text-sm text-red-600 text-center">
                    {speechState.error}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceConversationLoop;
