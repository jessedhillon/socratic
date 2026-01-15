import React, { useState } from 'react';
import {
  ChatInterface,
  ChatMessage,
  type ChatMessageData,
} from '../components/assessment';

const sampleMessages: ChatMessageData[] = [
  {
    id: '1',
    type: 'interviewer',
    content:
      "Hello! I'm here to help assess your understanding of React hooks. Let's start with a foundational question: Can you explain what the useEffect hook does and when you would use it?",
    timestamp: new Date().toISOString(),
  },
  {
    id: '2',
    type: 'learner',
    content:
      'useEffect is a hook that lets you perform side effects in function components. You use it for things like data fetching, subscriptions, or manually changing the DOM. It runs after the component renders.',
    timestamp: new Date().toISOString(),
  },
  {
    id: '3',
    type: 'interviewer',
    content:
      'Good explanation! Can you tell me about the dependency array and what happens if you pass an empty array versus no array at all?',
    timestamp: new Date().toISOString(),
  },
  {
    id: '4',
    type: 'system',
    content: 'Assessment is being recorded',
    timestamp: new Date().toISOString(),
  },
];

/**
 * Development test page for chat components.
 * Remove before merging to production.
 */
const DevChatTestPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessageData[]>(sampleMessages);
  const [isWaiting, setIsWaiting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  const demoStreaming = () => {
    const streamText =
      'This message is being streamed token by token, simulating how the AI response will appear in real-time during an assessment.';
    const tokens = streamText.split(' ');

    // Add empty streaming message
    const msgId = `stream-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: msgId,
        type: 'interviewer',
        content: '',
        isStreaming: true,
      },
    ]);
    setIsWaiting(true);

    // Stream tokens one at a time
    let currentContent = '';
    tokens.forEach((token, i) => {
      setTimeout(() => {
        currentContent += (i === 0 ? '' : ' ') + token;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId ? { ...m, content: currentContent } : m
          )
        );

        // Finish streaming on last token
        if (i === tokens.length - 1) {
          setTimeout(() => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === msgId ? { ...m, isStreaming: false } : m
              )
            );
            setIsWaiting(false);
          }, 200);
        }
      }, i * 100); // 100ms per token
    });
  };

  const handleSendMessage = (content: string) => {
    // Add learner message
    const learnerMsg: ChatMessageData = {
      id: `msg-${Date.now()}`,
      type: 'learner',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, learnerMsg]);
    setIsWaiting(true);

    // Simulate AI response after delay
    setTimeout(() => {
      const aiMsg: ChatMessageData = {
        id: `msg-${Date.now()}`,
        type: 'interviewer',
        content: `Thanks for that response about "${content.slice(0, 30)}...". That's an interesting perspective. Can you elaborate further?`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, aiMsg]);
      setIsWaiting(false);
    }, 2000);
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-semibold">Chat Components Test</h1>
        <p className="text-sm text-gray-500">Development testing page</p>
      </header>

      {/* Controls */}
      <div className="bg-gray-100 px-6 py-3 border-b flex gap-4 items-center">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isWaiting}
            onChange={(e) => setIsWaiting(e.target.checked)}
          />
          <span className="text-sm">isWaitingForResponse</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isComplete}
            onChange={(e) => setIsComplete(e.target.checked)}
          />
          <span className="text-sm">isAssessmentComplete</span>
        </label>
        <button
          onClick={() => setMessages(sampleMessages)}
          className="text-sm px-3 py-1 bg-gray-200 rounded hover:bg-gray-300"
        >
          Reset Messages
        </button>
        <button
          onClick={demoStreaming}
          disabled={isWaiting}
          className="text-sm px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
        >
          Demo Streaming
        </button>
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

      {/* Full ChatInterface */}
      <div className="flex-1 overflow-hidden">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          isWaitingForResponse={isWaiting}
          isAssessmentComplete={isComplete}
        />
      </div>
    </div>
  );
};

export default DevChatTestPage;
