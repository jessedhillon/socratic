import React from 'react';

export type MessageRole = 'learner' | 'interviewer' | 'system';

export interface ChatMessageProps {
  role: MessageRole;
  content: string;
  timestamp?: Date;
  isStreaming?: boolean;
}

/**
 * Individual chat message component.
 * Displays messages with different styling based on the speaker role.
 */
const ChatMessage: React.FC<ChatMessageProps> = ({
  role,
  content,
  timestamp,
  isStreaming = false,
}) => {
  const isAI = role === 'interviewer';
  const isSystem = role === 'system';

  const containerClasses = isAI
    ? 'justify-start'
    : isSystem
      ? 'justify-center'
      : 'justify-end';

  const bubbleClasses = isAI
    ? 'bg-white border border-gray-200 text-gray-800'
    : isSystem
      ? 'bg-gray-100 text-gray-600 text-sm italic'
      : 'bg-blue-600 text-white';

  const labelText = isAI ? 'Interviewer' : isSystem ? 'System' : 'You';

  return (
    <div className={`flex ${containerClasses} mb-4`}>
      <div className={`max-w-[80%] ${isSystem ? 'max-w-full' : ''}`}>
        <div className="flex items-center gap-2 mb-1">
          <span
            className={`text-xs ${isAI ? 'text-gray-500' : isSystem ? 'text-gray-400' : 'text-blue-600'}`}
          >
            {labelText}
          </span>
          {timestamp && (
            <span className="text-xs text-gray-400">
              {timestamp.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
        </div>
        <div
          className={`rounded-lg px-4 py-2 ${bubbleClasses} ${isStreaming ? 'animate-pulse' : ''}`}
        >
          <p className="whitespace-pre-wrap">{content}</p>
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-current animate-blink" />
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
