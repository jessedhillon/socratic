import React, { useState, useRef, useEffect } from 'react';
import ChatMessage, { MessageRole } from './ChatMessage';
import useSSE from '../hooks/useSSE';
import { completeAssessment as completeAssessmentApi } from '../api/sdk.gen';

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

interface AssessmentProps {
  assignmentId: string;
  attemptId?: string;
  objectiveTitle?: string;
  onAttemptCreated?: (attemptId: string) => void;
  onComplete?: () => void;
}

/**
 * Main assessment chat interface component.
 * Handles the Socratic dialogue between the learner and AI interviewer.
 */
const Assessment: React.FC<AssessmentProps> = ({
  assignmentId,
  attemptId: initialAttemptId,
  objectiveTitle: initialTitle,
  onAttemptCreated,
  onComplete,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [attemptId, setAttemptId] = useState<string | undefined>(
    initialAttemptId
  );
  const [objectiveTitle, setObjectiveTitle] = useState(
    initialTitle || 'Assessment'
  );
  const [streamingContent, setStreamingContent] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { isStreaming, stream, error } = useSSE();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Start assessment when component mounts without an attempt ID
  useEffect(() => {
    if (!attemptId) {
      startAssessment();
    }
  }, []);

  const startAssessment = async () => {
    setStreamingContent('');

    await stream(`/api/assessments/${assignmentId}/start`, {
      method: 'POST',
      onToken: (token) => {
        setStreamingContent((prev) => prev + token);
      },
      onDone: (data) => {
        if (data && typeof data === 'object' && 'attempt_id' in data) {
          const responseData = data as {
            attempt_id: string;
            objective_title: string;
          };
          setAttemptId(responseData.attempt_id);
          setObjectiveTitle(responseData.objective_title || 'Assessment');
          onAttemptCreated?.(responseData.attempt_id);
        }

        // Move streaming content to messages
        setMessages((prev) => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            role: 'interviewer',
            content: streamingContent,
            timestamp: new Date(),
          },
        ]);
        setStreamingContent('');
      },
      onError: (err) => {
        console.error('Failed to start assessment:', err);
      },
    });
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || !attemptId || isStreaming) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'learner',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setStreamingContent('');

    await stream(`/api/assessments/${attemptId}/message`, {
      method: 'POST',
      body: { content: userMessage.content },
      onToken: (token) => {
        setStreamingContent((prev) => prev + token);
      },
      onDone: () => {
        // Move streaming content to messages
        setMessages((prev) => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            role: 'interviewer',
            content: streamingContent,
            timestamp: new Date(),
          },
        ]);
        setStreamingContent('');
      },
      onError: (err) => {
        console.error('Failed to send message:', err);
      },
    });

    // Focus input after sending
    inputRef.current?.focus();
  };

  const completeAssessment = async () => {
    if (!attemptId) return;

    try {
      await completeAssessmentApi({
        path: { attempt_id: attemptId },
        throwOnError: true,
      });
      setIsComplete(true);
      onComplete?.();
    } catch (err) {
      console.error('Failed to complete assessment:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">
            {objectiveTitle}
          </h2>
          <p className="text-sm text-gray-500">Socratic Assessment</p>
        </div>
        {attemptId && !isComplete && (
          <button
            onClick={completeAssessment}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            Complete Assessment
          </button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-red-700">{error.message}</p>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            role={message.role}
            content={message.content}
            timestamp={message.timestamp}
          />
        ))}

        {/* Streaming message */}
        {streamingContent && (
          <ChatMessage
            role="interviewer"
            content={streamingContent}
            isStreaming={true}
          />
        )}

        {isComplete && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-md text-center">
            <p className="text-green-700 font-medium">Assessment completed!</p>
            <p className="text-green-600 text-sm mt-1">
              Your responses have been recorded for evaluation.
            </p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {!isComplete && (
        <div className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your response..."
              disabled={isStreaming || !attemptId}
              className="flex-1 resize-none rounded-md border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              rows={2}
            />
            <button
              onClick={sendMessage}
              disabled={isStreaming || !inputValue.trim() || !attemptId}
              className="px-6 py-2 font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-blue-300 disabled:cursor-not-allowed"
            >
              {isStreaming ? 'Sending...' : 'Send'}
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      )}
    </div>
  );
};

export default Assessment;
