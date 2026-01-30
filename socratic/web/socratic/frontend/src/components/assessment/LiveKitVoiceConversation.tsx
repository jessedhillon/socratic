/**
 * LiveKit-based real-time voice conversation component.
 *
 * Replaces the record/playback UI with a real-time voice interface using LiveKit.
 * Manages room connection, displays connection status, and shows agent speaking state.
 */

import React, { useEffect, useCallback, useState, useRef } from 'react';
import {
  useLiveKitRoom,
  type LiveKitConnectionState,
} from '../../hooks/useLiveKitRoom';
import ChatMessage, { type ChatMessageData } from './ChatMessage';

export interface LiveKitVoiceConversationProps {
  /** LiveKit server URL */
  serverUrl: string;
  /** Access token for the room */
  token: string;
  /** Chat messages to display */
  messages: ChatMessageData[];
  /** Whether the assessment is complete */
  isAssessmentComplete: boolean;
  /** Whether the user is leaving the page */
  isLeavingPage?: boolean;
  /** Callback when connection state changes */
  onConnectionStateChange?: (state: LiveKitConnectionState) => void;
  /** Callback when transcription segments are received */
  onTranscription?: (
    segments: Array<{ id: string; text: string; isFinal: boolean }>,
    participantIdentity: string,
    isLocal: boolean
  ) => void;
  /** Callback when a data channel message is received */
  onDataReceived?: (data: Record<string, unknown>, topic?: string) => void;
  /** Content to render above the input area (e.g., closure banner) */
  inputHeaderContent?: React.ReactNode;
}

/**
 * Real-time voice conversation component using LiveKit.
 *
 * Features:
 * - Automatic room connection with token
 * - Real-time bidirectional voice communication
 * - Visual indicators for connection state and agent speaking
 * - Microphone toggle control
 * - Graceful handling of connection issues
 *
 * @example
 * ```tsx
 * <LiveKitVoiceConversation
 *   serverUrl="wss://your-livekit-server.com"
 *   token={roomToken}
 *   messages={messages}
 *   isAssessmentComplete={false}
 *   onConnectionStateChange={(state) => console.log('Connection:', state)}
 * />
 * ```
 */
const LiveKitVoiceConversation: React.FC<LiveKitVoiceConversationProps> = ({
  serverUrl,
  token,
  messages,
  isAssessmentComplete,
  isLeavingPage = false,
  onConnectionStateChange,
  onTranscription,
  onDataReceived,
  inputHeaderContent,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [hasConnected, setHasConnected] = useState(false);
  const [showThinkingIndicator, setShowThinkingIndicator] = useState(false);
  const thinkingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Delay before showing the thinking indicator after learner finishes speaking
  const THINKING_DELAY_MS = 750;

  const {
    connectionState,
    isMicrophoneEnabled,
    isAgentSpeaking,
    error,
    connect,
    disconnect,
    toggleMicrophone,
  } = useLiveKitRoom({
    serverUrl,
    token,
    autoConnect: true,
    onConnectionStateChange: (state) => {
      onConnectionStateChange?.(state);
      if (state === 'connected') {
        setHasConnected(true);
      }
    },
    onTranscription,
    onDataReceived,
  });

  // Disconnect when assessment completes or user leaves
  useEffect(() => {
    if ((isAssessmentComplete || isLeavingPage) && hasConnected) {
      disconnect();
    }
  }, [isAssessmentComplete, isLeavingPage, hasConnected, disconnect]);

  // Show thinking indicator after the learner finishes speaking, until the
  // agent's response arrives.
  useEffect(() => {
    const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null;
    const learnerDone = lastMsg?.type === 'learner' && !lastMsg.isStreaming;

    if (learnerDone) {
      thinkingTimerRef.current = setTimeout(() => {
        setShowThinkingIndicator(true);
      }, THINKING_DELAY_MS);
    } else {
      // Either no messages, learner still streaming, or agent responded
      if (thinkingTimerRef.current) {
        clearTimeout(thinkingTimerRef.current);
        thinkingTimerRef.current = null;
      }
      setShowThinkingIndicator(false);
    }

    return () => {
      if (thinkingTimerRef.current) {
        clearTimeout(thinkingTimerRef.current);
        thinkingTimerRef.current = null;
      }
    };
  }, [messages]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Reconnect handler
  const handleReconnect = useCallback(() => {
    connect();
  }, [connect]);

  // Connection status display
  const getConnectionStatusDisplay = (): {
    text: string;
    className: string;
    icon: React.ReactNode;
  } => {
    switch (connectionState) {
      case 'connecting':
        return {
          text: 'Connecting...',
          className: 'bg-yellow-100 text-yellow-700',
          icon: (
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
          ),
        };
      case 'connected':
        return {
          text: 'Connected',
          className: 'bg-green-100 text-green-700',
          icon: (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          ),
        };
      case 'reconnecting':
        return {
          text: 'Reconnecting...',
          className: 'bg-orange-100 text-orange-700',
          icon: (
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
          ),
        };
      case 'error':
        return {
          text: error || 'Connection error',
          className: 'bg-red-100 text-red-700',
          icon: (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
            </svg>
          ),
        };
      default:
        return {
          text: 'Disconnected',
          className: 'bg-gray-100 text-gray-700',
          icon: (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11H7v-2h10v2z" />
            </svg>
          ),
        };
    }
  };

  const statusDisplay = getConnectionStatusDisplay();

  return (
    <div className="flex flex-col h-full">
      {/* Connection status bar */}
      {!isAssessmentComplete && (
        <div
          className={`flex items-center justify-between px-4 py-2 ${statusDisplay.className}`}
        >
          <div className="flex items-center gap-2">
            {statusDisplay.icon}
            <span className="text-sm font-medium">{statusDisplay.text}</span>
          </div>

          {/* Microphone toggle */}
          {connectionState === 'connected' && (
            <button
              onClick={toggleMicrophone}
              className={`p-2 rounded-full transition-colors ${
                isMicrophoneEnabled
                  ? 'bg-green-500 text-white hover:bg-green-600'
                  : 'bg-red-500 text-white hover:bg-red-600'
              }`}
              title={
                isMicrophoneEnabled ? 'Mute microphone' : 'Unmute microphone'
              }
            >
              {isMicrophoneEnabled ? (
                <svg
                  className="w-5 h-5"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                </svg>
              ) : (
                <svg
                  className="w-5 h-5"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z" />
                </svg>
              )}
            </button>
          )}

          {/* Reconnect button for error state */}
          {connectionState === 'error' && (
            <button
              onClick={handleReconnect}
              className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
            >
              Reconnect
            </button>
          )}
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 bg-gray-50">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 && connectionState === 'connecting' && (
            <div className="text-center text-gray-500 py-8">
              Connecting to assessment room...
            </div>
          )}

          {messages.length === 0 && connectionState === 'connected' && (
            <div className="text-center text-gray-500 py-8">
              The assessment will begin shortly...
            </div>
          )}

          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              isSpeaking={isAgentSpeaking && message.type === 'interviewer'}
            />
          ))}

          {/* Agent thinking indicator — shown after learner stops speaking, hidden when disconnected */}
          {showThinkingIndicator && connectionState === 'connected' && (
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
            ) : connectionState === 'connected' ? (
              <div className="text-center text-gray-500 py-2">
                <div className="flex items-center justify-center gap-2">
                  {isMicrophoneEnabled ? (
                    <>
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                      </span>
                      <span>Microphone active - speak to respond</span>
                    </>
                  ) : (
                    <>
                      <span className="relative flex h-3 w-3">
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                      </span>
                      <span>Microphone muted - click to unmute</span>
                    </>
                  )}
                </div>
              </div>
            ) : connectionState === 'error' ? (
              <div className="text-center text-red-600 py-2">
                Connection failed. Please try reconnecting.
              </div>
            ) : (
              <div className="text-center text-gray-500 py-2">
                Connecting to voice channel...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LiveKitVoiceConversation;
