import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAssessmentStream, type ConnectionState } from '../../hooks';
import {
  ChatInterface,
  type ChatMessageData as Message,
} from '../../components/assessment';

const connectionColors: Record<ConnectionState, string> = {
  disconnected: 'bg-gray-400',
  connecting: 'bg-yellow-400',
  connected: 'bg-green-500',
  error: 'bg-red-500',
};

/**
 * Development test page for real API integration with EventSource streaming.
 *
 * This page tests the actual backend API, unlike DevChatTestPage which uses mocks.
 * Requires:
 * - Backend running (process-compose up)
 * - Valid assignment ID in the database
 * - Authenticated session (logged in as learner)
 */
const DevApiTestPage: React.FC = () => {
  const {
    startAssessment,
    connectStream,
    sendMessage,
    completeAssessment,
    disconnect,
    connectionState,
  } = useAssessmentStream();

  const [assignmentId, setAssignmentId] = useState('');
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [objectiveTitle, setObjectiveTitle] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const streamingMessageId = useRef<string | null>(null);
  const messageIdCounter = useRef(0);

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, 12);
    setLogs((prev) => [...prev, `[${timestamp}] ${message}`]);
  }, []);

  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1;
    return `msg-${messageIdCounter.current}`;
  }, []);

  const handleStart = async () => {
    if (!assignmentId.trim()) {
      setError('Please enter an assignment ID');
      return;
    }

    setError(null);
    addLog(`Starting assessment for assignment: ${assignmentId}`);

    try {
      const response = await startAssessment(assignmentId);
      addLog(`Assessment started: attempt_id=${response.attempt_id}`);

      setAttemptId(response.attempt_id);
      setObjectiveTitle(response.objective_title);
      setMessages([]);

      // Connect to the event stream
      addLog('Connecting to event stream...');
      connectStream(response.attempt_id, {
        onToken: (content: string) => {
          // Create new streaming message if needed
          if (!streamingMessageId.current) {
            const newId = generateMessageId();
            streamingMessageId.current = newId;
            setMessages((prev) => [
              ...prev,
              {
                id: newId,
                type: 'interviewer',
                content: '',
                isStreaming: true,
              },
            ]);
          }
          // Capture ID before async state update
          const currentId = streamingMessageId.current;
          // Append token to streaming message
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === currentId
                ? { ...msg, content: msg.content + content }
                : msg
            )
          );
        },
        onMessageDone: () => {
          addLog('Message complete');
          // Capture the ID before the async state update
          // (the callback reads .current at execution time, which would be null)
          const currentId = streamingMessageId.current;
          if (currentId) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === currentId ? { ...msg, isStreaming: false } : msg
              )
            );
            streamingMessageId.current = null;
          }
          setIsWaitingForResponse(false);
        },
        onComplete: (evaluationId?: string) => {
          addLog(`Assessment complete! evaluation_id=${evaluationId || 'N/A'}`);
          setMessages((prev) => [
            ...prev,
            {
              id: generateMessageId(),
              type: 'system',
              content: 'Assessment completed successfully.',
            },
          ]);
        },
        onError: (message: string, recoverable: boolean) => {
          addLog(`Error: ${message} (recoverable: ${recoverable})`);
          setError(message);
          if (!recoverable) {
            setIsWaitingForResponse(false);
          }
        },
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      addLog(`Failed to start: ${message}`);
      setError(message);
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!attemptId) {
      setError('No active assessment');
      return;
    }

    addLog(`Sending message: "${content.slice(0, 50)}..."`);
    setIsWaitingForResponse(true);

    // Add learner message to UI
    setMessages((prev) => [
      ...prev,
      { id: generateMessageId(), type: 'learner', content },
    ]);

    try {
      const response = await sendMessage(attemptId, content);
      addLog(`Message accepted: message_id=${response.message_id}`);
      // Response will stream via EventSource
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      addLog(`Failed to send: ${message}`);
      setError(message);
      setIsWaitingForResponse(false);
    }
  };

  const handleComplete = async () => {
    if (!attemptId) return;

    addLog('Completing assessment...');
    try {
      const response = await completeAssessment(attemptId);
      addLog(`Assessment completed: status=${response.status}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      addLog(`Failed to complete: ${message}`);
      setError(message);
    }
  };

  const handleDisconnect = () => {
    addLog('Disconnecting...');
    disconnect();
    setAttemptId(null);
    setObjectiveTitle(null);
  };

  // Auto-scroll logs
  const logsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-semibold">Assessment API Test</h1>
        <p className="text-sm text-gray-500">
          E2E testing with real backend and EventSource streaming
        </p>
      </header>

      {/* Status bar */}
      <div className="bg-gray-50 px-6 py-3 border-b">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium">Connection:</span>
          <span
            className={`px-3 py-1 rounded-full text-white text-sm font-medium ${connectionColors[connectionState]}`}
          >
            {connectionState}
          </span>
          {attemptId && (
            <span className="text-sm text-gray-600">
              Attempt:{' '}
              <code className="bg-gray-200 px-1 rounded">{attemptId}</code>
            </span>
          )}
          {objectiveTitle && (
            <span className="text-sm text-gray-600">
              Objective: {objectiveTitle}
            </span>
          )}
        </div>
        {error && (
          <div className="mt-2 text-red-600 text-sm">Error: {error}</div>
        )}
      </div>

      {/* Controls */}
      <div className="bg-gray-100 px-6 py-3 border-b flex items-center gap-4">
        {!attemptId ? (
          <>
            <input
              type="text"
              placeholder="Assignment ID (e.g., asgn$...)"
              value={assignmentId}
              onChange={(e) => setAssignmentId(e.target.value)}
              className="flex-1 max-w-md px-3 py-2 border rounded text-sm"
            />
            <button
              onClick={handleStart}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
            >
              Start Assessment
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleComplete}
              disabled={isWaitingForResponse}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300 text-sm"
            >
              Complete Assessment
            </button>
            <button
              onClick={handleDisconnect}
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
            >
              Disconnect
            </button>
          </>
        )}
      </div>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat interface */}
        <div className="flex-1 overflow-hidden">
          <ChatInterface
            messages={messages}
            onSendMessage={handleSendMessage}
            isWaitingForResponse={isWaitingForResponse}
            isAssessmentComplete={
              connectionState === 'disconnected' && attemptId !== null
            }
            disabled={!attemptId || connectionState !== 'connected'}
          />
        </div>

        {/* Log panel */}
        <div className="w-96 border-l bg-gray-900 text-green-400 flex flex-col">
          <div className="px-4 py-2 border-b border-gray-700 text-sm font-medium">
            Event Log
          </div>
          <div
            ref={logsRef}
            className="flex-1 overflow-y-auto p-4 font-mono text-xs"
          >
            {logs.length === 0 ? (
              <div className="text-gray-500">Logs will appear here...</div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="mb-1 whitespace-pre-wrap">
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DevApiTestPage;
