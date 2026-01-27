import React, { useState, useCallback, useRef, useEffect } from 'react';
import { login } from '../../api/sdk.gen';
import { getAuthToken } from '../../auth';
import {
  LiveKitVoiceConversation,
  type ChatMessageData as Message,
} from '../../components/assessment';
import {
  useLiveKitRoom,
  type LiveKitConnectionState,
} from '../../hooks/useLiveKitRoom';

const connectionColors: Record<LiveKitConnectionState, string> = {
  disconnected: 'bg-gray-400',
  connecting: 'bg-yellow-400',
  connected: 'bg-green-500',
  reconnecting: 'bg-orange-400',
  error: 'bg-red-500',
};

/**
 * Development test page for LiveKit real-time voice integration.
 *
 * This page exercises:
 * - useLiveKitRoom hook (connection, mic toggle, agent speaking state)
 * - LiveKitVoiceConversation component (UI, status bar, messages)
 * - LiveKit API client (room token fetching)
 *
 * Requires:
 * - Backend running (process-compose up)
 * - LiveKit server running (via process-compose or standalone)
 * - Valid attempt ID in the database
 */
const DevLiveKitTestPage: React.FC = () => {
  // Auth state
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [userName, setUserName] = useState<string | null>(null);

  // LiveKit token state
  const [attemptId, setAttemptId] = useState('');
  const [roomToken, setRoomToken] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [roomName, setRoomName] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);

  // Component test state
  const [activeTab, setActiveTab] = useState<'hook' | 'component'>('hook');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAssessmentComplete, setIsAssessmentComplete] = useState(false);
  const messageIdCounter = useRef(0);

  // Logs
  const [logs, setLogs] = useState<string[]>([]);
  const logsRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, 12);
    setLogs((prev) => [...prev, `[${timestamp}] ${message}`]);
  }, []);

  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1;
    return `msg-${messageIdCounter.current}`;
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  // Check if already logged in on mount
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      setIsLoggedIn(true);
      setUserName('(cached session)');
      addLog('Using cached auth token');
    }
  }, [addLog]);

  // Auto-login with dev credentials
  const handleLogin = async () => {
    setLoginError(null);
    addLog('Logging in with dev credentials...');
    try {
      const { data, error } = await login({
        body: {
          email: 'jesse@dhillon.com',
          password: 'U89mKIJYh2sVweE2',
        },
      });

      if (error || !data) {
        throw new Error('Login failed');
      }

      localStorage.setItem('access_token', data.token.access_token);
      setIsLoggedIn(true);
      setUserName(data.user.name);
      addLog(`Logged in as ${data.user.name} (${data.user.user_id})`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setLoginError(message);
      addLog(`Login failed: ${message}`);
    }
  };

  // Fetch LiveKit room token (not in generated SDK yet, use fetch)
  const handleGetToken = async () => {
    if (!attemptId.trim()) {
      setTokenError('Enter an attempt ID');
      return;
    }
    setTokenError(null);
    addLog(`Fetching room token for attempt: ${attemptId}`);

    try {
      const token = getAuthToken();
      const response = await fetch(
        `/api/livekit/rooms/${encodeURIComponent(attemptId)}/token`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      );

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(
          (errData as { detail?: string }).detail || `HTTP ${response.status}`
        );
      }

      const data = (await response.json()) as {
        token: string;
        url: string;
        room_name: string;
        attempt_id: string;
      };

      setRoomToken(data.token);
      setServerUrl(data.url);
      setRoomName(data.room_name);
      addLog(`Got token for room: ${data.room_name}`);
      addLog(`Server URL: ${data.url}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to get token';
      setTokenError(message);
      addLog(`Token error: ${message}`);
    }
  };

  // Manual URL/token entry (for testing without backend)
  const [manualUrl, setManualUrl] = useState('ws://localhost:7880');
  const [manualToken, setManualToken] = useState('');
  const handleManualConnect = () => {
    if (!manualToken.trim()) {
      addLog('Enter a token');
      return;
    }
    setServerUrl(manualUrl);
    setRoomToken(manualToken);
    setRoomName('manual');
    addLog(`Using manual connection: ${manualUrl}`);
  };

  // Stable callbacks for hook (avoid re-render loops)
  const onHookConnectionChange = useCallback(
    (state: LiveKitConnectionState) => {
      addLog(`[hook] Connection state: ${state}`);
    },
    [addLog]
  );

  const onHookAgentSpeakingChange = useCallback(
    (speaking: boolean) => {
      addLog(`[hook] Agent speaking: ${speaking}`);
    },
    [addLog]
  );

  const onHookTranscription = useCallback(
    (text: string, isFinal: boolean, participantId: string) => {
      addLog(
        `[hook] Transcription (${isFinal ? 'final' : 'partial'}): "${text}" from ${participantId}`
      );
    },
    [addLog]
  );

  // Hook test (direct hook usage)
  const hookRoom = useLiveKitRoom({
    serverUrl: serverUrl || '',
    token: roomToken || '',
    onConnectionStateChange: onHookConnectionChange,
    onAgentSpeakingChange: onHookAgentSpeakingChange,
    onTranscription: onHookTranscription,
  });

  // Add mock messages for component testing
  const addMockLearnerMessage = () => {
    setMessages((prev) => [
      ...prev,
      {
        id: generateMessageId(),
        type: 'learner' as const,
        content: 'This is a test learner message.',
      },
    ]);
    addLog('[component] Added mock learner message');
  };

  const addMockInterviewerMessage = () => {
    setMessages((prev) => [
      ...prev,
      {
        id: generateMessageId(),
        type: 'interviewer' as const,
        content:
          'This is a test interviewer response. The agent would normally generate this through voice.',
      },
    ]);
    addLog('[component] Added mock interviewer message');
  };

  const clearMessages = () => {
    setMessages([]);
    setIsAssessmentComplete(false);
    addLog('[component] Cleared messages');
  };

  const handleReset = () => {
    hookRoom.disconnect();
    setRoomToken(null);
    setServerUrl(null);
    setRoomName(null);
    setMessages([]);
    setIsAssessmentComplete(false);
    addLog('Reset all state');
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-semibold">LiveKit Voice Test</h1>
        <p className="text-sm text-gray-500">
          Test useLiveKitRoom hook and LiveKitVoiceConversation component
        </p>
      </header>

      {/* Auth + token bar */}
      <div className="bg-gray-50 px-6 py-3 border-b space-y-3">
        {/* Auth row */}
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium w-16">Auth:</span>
          {isLoggedIn ? (
            <span className="text-sm text-green-700">
              Logged in as <strong>{userName}</strong>
            </span>
          ) : (
            <>
              <button
                onClick={handleLogin}
                className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
              >
                Login (dev credentials)
              </button>
              {loginError && (
                <span className="text-sm text-red-600">{loginError}</span>
              )}
            </>
          )}
        </div>

        {/* Token row - via API */}
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium w-16">API:</span>
          <input
            type="text"
            placeholder="Attempt ID (e.g., attm$...)"
            value={attemptId}
            onChange={(e) => setAttemptId(e.target.value)}
            className="flex-1 max-w-xs px-3 py-1.5 border rounded text-sm"
            disabled={!isLoggedIn}
          />
          <button
            onClick={handleGetToken}
            disabled={!isLoggedIn}
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:bg-gray-300"
          >
            Get Token
          </button>
          {tokenError && (
            <span className="text-sm text-red-600">{tokenError}</span>
          )}
        </div>

        {/* Token row - manual */}
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium w-16">Manual:</span>
          <input
            type="text"
            placeholder="Server URL"
            value={manualUrl}
            onChange={(e) => setManualUrl(e.target.value)}
            className="w-48 px-3 py-1.5 border rounded text-sm"
          />
          <input
            type="text"
            placeholder="Access token"
            value={manualToken}
            onChange={(e) => setManualToken(e.target.value)}
            className="flex-1 max-w-xs px-3 py-1.5 border rounded text-sm"
          />
          <button
            onClick={handleManualConnect}
            className="px-3 py-1 bg-gray-600 text-white rounded text-sm hover:bg-gray-700"
          >
            Use
          </button>
        </div>

        {/* Connection status */}
        {roomToken && (
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium w-16">Room:</span>
            <code className="text-sm bg-gray-200 px-2 py-0.5 rounded">
              {roomName}
            </code>
            <span className="text-sm text-gray-500">
              Token: {roomToken.slice(0, 20)}...
            </span>
            <button
              onClick={handleReset}
              className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
            >
              Reset
            </button>
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="bg-white border-b px-6">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab('hook')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'hook'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            useLiveKitRoom Hook
          </button>
          <button
            onClick={() => setActiveTab('component')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'component'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            LiveKitVoiceConversation Component
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel - test area */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {activeTab === 'hook' ? (
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Hook state display */}
              <section>
                <h2 className="text-lg font-medium mb-3">Hook State</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white border rounded p-4">
                    <div className="text-sm text-gray-500 mb-1">Connection</div>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-white text-sm font-medium ${connectionColors[hookRoom.connectionState]}`}
                    >
                      {hookRoom.connectionState}
                    </span>
                  </div>
                  <div className="bg-white border rounded p-4">
                    <div className="text-sm text-gray-500 mb-1">Microphone</div>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-white text-sm font-medium ${
                        hookRoom.isMicrophoneEnabled
                          ? 'bg-green-500'
                          : 'bg-gray-400'
                      }`}
                    >
                      {hookRoom.isMicrophoneEnabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <div className="bg-white border rounded p-4">
                    <div className="text-sm text-gray-500 mb-1">
                      Agent Speaking
                    </div>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-white text-sm font-medium ${
                        hookRoom.isAgentSpeaking ? 'bg-blue-500' : 'bg-gray-400'
                      }`}
                    >
                      {hookRoom.isAgentSpeaking ? 'Speaking' : 'Silent'}
                    </span>
                  </div>
                  <div className="bg-white border rounded p-4">
                    <div className="text-sm text-gray-500 mb-1">Error</div>
                    <span className="text-sm">
                      {hookRoom.error || (
                        <span className="text-gray-400">None</span>
                      )}
                    </span>
                  </div>
                </div>
              </section>

              {/* Hook controls */}
              <section>
                <h2 className="text-lg font-medium mb-3">Controls</h2>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => {
                      addLog('[hook] Connecting...');
                      hookRoom.connect();
                    }}
                    disabled={
                      !roomToken ||
                      hookRoom.connectionState === 'connected' ||
                      hookRoom.connectionState === 'connecting'
                    }
                    className="px-4 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:bg-gray-300"
                  >
                    Connect
                  </button>
                  <button
                    onClick={() => {
                      addLog('[hook] Disconnecting...');
                      hookRoom.disconnect();
                    }}
                    disabled={hookRoom.connectionState === 'disconnected'}
                    className="px-4 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600 disabled:bg-gray-300"
                  >
                    Disconnect
                  </button>
                  <button
                    onClick={() => {
                      addLog('[hook] Toggling microphone...');
                      hookRoom.toggleMicrophone();
                    }}
                    disabled={hookRoom.connectionState !== 'connected'}
                    className="px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:bg-gray-300"
                  >
                    Toggle Mic
                  </button>
                  <button
                    onClick={() => {
                      addLog('[hook] Enabling microphone...');
                      hookRoom.enableMicrophone();
                    }}
                    disabled={
                      hookRoom.connectionState !== 'connected' ||
                      hookRoom.isMicrophoneEnabled
                    }
                    className="px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:bg-gray-300"
                  >
                    Enable Mic
                  </button>
                  <button
                    onClick={() => {
                      addLog('[hook] Disabling microphone...');
                      hookRoom.disableMicrophone();
                    }}
                    disabled={
                      hookRoom.connectionState !== 'connected' ||
                      !hookRoom.isMicrophoneEnabled
                    }
                    className="px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:bg-gray-300"
                  >
                    Disable Mic
                  </button>
                </div>
              </section>

              {/* Room info */}
              {hookRoom.room && (
                <section>
                  <h2 className="text-lg font-medium mb-3">Room Info</h2>
                  <div className="bg-white border rounded p-4 text-sm space-y-1">
                    <div>
                      <span className="text-gray-500">Name: </span>
                      {hookRoom.room.name || 'N/A'}
                    </div>
                    <div>
                      <span className="text-gray-500">SID: </span>
                      {hookRoom.room.sid || 'N/A'}
                    </div>
                    <div>
                      <span className="text-gray-500">Participants: </span>
                      {hookRoom.room.numParticipants}
                    </div>
                    <div>
                      <span className="text-gray-500">Local identity: </span>
                      {hookRoom.room.localParticipant?.identity || 'N/A'}
                    </div>
                  </div>
                </section>
              )}
            </div>
          ) : (
            /* Component tab */
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Component controls */}
              <div className="bg-gray-100 px-4 py-2 border-b flex items-center gap-3">
                <button
                  onClick={addMockLearnerMessage}
                  className="px-3 py-1 bg-indigo-500 text-white rounded text-sm hover:bg-indigo-600"
                >
                  + Learner Msg
                </button>
                <button
                  onClick={addMockInterviewerMessage}
                  className="px-3 py-1 bg-purple-500 text-white rounded text-sm hover:bg-purple-600"
                >
                  + Interviewer Msg
                </button>
                <button
                  onClick={clearMessages}
                  className="px-3 py-1 bg-gray-500 text-white rounded text-sm hover:bg-gray-600"
                >
                  Clear
                </button>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={isAssessmentComplete}
                    onChange={(e) => {
                      setIsAssessmentComplete(e.target.checked);
                      addLog(
                        `[component] Assessment complete: ${e.target.checked}`
                      );
                    }}
                  />
                  Assessment Complete
                </label>
              </div>

              {/* LiveKitVoiceConversation */}
              <div className="flex-1 overflow-hidden">
                {roomToken && serverUrl ? (
                  <LiveKitVoiceConversation
                    serverUrl={serverUrl}
                    token={roomToken}
                    messages={messages}
                    isAssessmentComplete={isAssessmentComplete}
                    onConnectionStateChange={(state) => {
                      addLog(`[component] Connection state: ${state}`);
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500">
                    <div className="text-center">
                      <p className="text-lg mb-2">No room token</p>
                      <p className="text-sm">
                        Login and fetch a token above, or enter one manually
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right panel - log */}
        <div className="w-96 border-l bg-gray-900 text-green-400 flex flex-col">
          <div className="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
            <span className="text-sm font-medium">Event Log</span>
            <button
              onClick={() => setLogs([])}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              Clear
            </button>
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

export default DevLiveKitTestPage;
