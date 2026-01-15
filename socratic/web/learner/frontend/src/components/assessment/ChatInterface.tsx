import React, { useRef, useEffect, useState } from 'react';
import ChatMessage, { type ChatMessageData } from './ChatMessage';

interface ChatInterfaceProps {
  messages: ChatMessageData[];
  onSendMessage: (content: string) => void;
  isWaitingForResponse: boolean;
  isAssessmentComplete: boolean;
  disabled?: boolean;
}

/**
 * Chat-style interface for assessment conversations.
 *
 * Features:
 * - Scrolling message history with auto-scroll
 * - Text input for learner responses
 * - Loading/thinking indicators
 * - Visual distinction between learner and interviewer messages
 */
const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  onSendMessage,
  isWaitingForResponse,
  isAssessmentComplete,
  disabled = false,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when not waiting for response
  useEffect(() => {
    if (!isWaitingForResponse && !isAssessmentComplete && !disabled) {
      inputRef.current?.focus();
    }
  }, [isWaitingForResponse, isAssessmentComplete, disabled]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (
      trimmed &&
      !isWaitingForResponse &&
      !isAssessmentComplete &&
      !disabled
    ) {
      onSendMessage(trimmed);
      setInputValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const canSend =
    inputValue.trim().length > 0 &&
    !isWaitingForResponse &&
    !isAssessmentComplete &&
    !disabled;

  // Check if we're streaming (last message is interviewer and still streaming)
  const isStreaming =
    messages.length > 0 &&
    messages[messages.length - 1].type === 'interviewer' &&
    messages[messages.length - 1].isStreaming;

  // Show typing indicator only when waiting but not streaming
  const showTypingIndicator = isWaitingForResponse && !isStreaming;

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 bg-gray-50">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 && !isWaitingForResponse && (
            <div className="text-center text-gray-500 py-8">
              The assessment will begin shortly...
            </div>
          )}

          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {/* Typing indicator */}
          {showTypingIndicator && (
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
      <div className="border-t bg-white px-4 py-4">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
          {isAssessmentComplete ? (
            <div className="text-center text-gray-500 py-2">
              Assessment complete. Your responses have been submitted.
            </div>
          ) : (
            <div className="flex gap-3 items-end">
              <div className="flex-1 relative">
                <textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    isWaitingForResponse
                      ? 'Waiting for response...'
                      : disabled
                        ? 'Input disabled'
                        : 'Type your response... (Enter to send, Shift+Enter for new line)'
                  }
                  disabled={isWaitingForResponse || disabled}
                  rows={1}
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:text-gray-500"
                  style={{
                    minHeight: '48px',
                    maxHeight: '200px',
                  }}
                />
              </div>
              <button
                type="submit"
                disabled={!canSend}
                className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;
