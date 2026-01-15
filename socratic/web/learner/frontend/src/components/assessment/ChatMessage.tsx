import React from 'react';
import type { UtteranceType } from '../../api';

export interface ChatMessageData {
  id: string;
  type: UtteranceType;
  content: string;
  timestamp?: string;
  isStreaming?: boolean;
}

interface ChatMessageProps {
  message: ChatMessageData;
}

/**
 * A single message bubble in the assessment chat interface.
 */
const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isLearner = message.type === 'learner';
  const isSystem = message.type === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-4">
        <div className="bg-gray-100 text-gray-600 text-sm px-4 py-2 rounded-lg max-w-md text-center">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isLearner ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] px-4 py-3 rounded-2xl ${
          isLearner
            ? 'bg-blue-600 text-white rounded-br-md'
            : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-md'
        }`}
      >
        {!isLearner && (
          <div className="text-xs text-gray-500 mb-1 font-medium">
            Interviewer
          </div>
        )}
        <div className="whitespace-pre-wrap">{message.content}</div>
        {message.isStreaming && (
          <span className="inline-block ml-1 animate-pulse">▊</span>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
