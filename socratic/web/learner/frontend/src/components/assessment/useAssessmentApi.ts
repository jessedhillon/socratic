import { useCallback, useRef, useState } from 'react';
import { client } from '../../api/client.gen';

/**
 * SSE event data types from the backend.
 */
interface TokenEvent {
  content: string;
}

interface StartDoneEvent {
  attempt_id: string;
  assignment_id: string;
  objective_id: string;
  objective_title: string;
}

interface MessageDoneEvent {
  // Empty for message completion
}

/**
 * Result from starting an assessment.
 */
export interface StartAssessmentResult {
  attemptId: string;
  assignmentId: string;
  objectiveId: string;
  objectiveTitle: string;
  initialMessage: string;
}

/**
 * Result from sending a message.
 */
export interface SendMessageResult {
  response: string;
}

/**
 * Parse SSE lines from a text chunk.
 * SSE format: "event: <type>\ndata: <json>\n\n"
 */
function parseSSEEvents(buffer: string): {
  events: Array<{ event: string; data: string }>;
  remainder: string;
} {
  const events: Array<{ event: string; data: string }> = [];
  const lines = buffer.split('\n');

  let currentEvent = '';
  let currentData = '';
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith('event:')) {
      currentEvent = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      currentData = line.slice(5).trim();
    } else if (line === '') {
      // Empty line marks end of an event
      if (currentEvent && currentData) {
        events.push({ event: currentEvent, data: currentData });
      }
      currentEvent = '';
      currentData = '';
    }
    i++;
  }

  // Return any incomplete event data as remainder
  let remainder = '';
  if (currentEvent || currentData) {
    // Reconstruct the incomplete lines
    const lastEventStart = buffer.lastIndexOf('event:');
    if (lastEventStart !== -1) {
      remainder = buffer.slice(lastEventStart);
    }
  }

  return { events, remainder };
}

/**
 * Hook for consuming SSE streams from assessment endpoints.
 *
 * The backend uses POST with SSE for assessment endpoints because:
 * 1. POST /api/assessments/{assignment_id}/start - creates attempt, streams orientation
 * 2. POST /api/assessments/{attempt_id}/message - sends learner message, streams response
 *
 * EventSource only supports GET, so we use fetch with streaming.
 */
export function useAssessmentApi() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedContent, setStreamedContent] = useState('');
  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * Get auth token from the client configuration.
   */
  const getAuthToken = useCallback((): string | null => {
    // The client stores auth in its internal config
    // Access via the interceptors or stored auth
    const config = client.getConfig();
    const auth = config.auth;
    if (typeof auth === 'string') {
      return auth;
    }
    // Check for bearer token in headers
    const headers = config.headers as Record<string, string> | undefined;
    if (headers?.Authorization) {
      return headers.Authorization.replace('Bearer ', '');
    }
    return null;
  }, []);

  /**
   * Make a streaming POST request and consume SSE events.
   */
  const streamPost = useCallback(
    async <T>(
      url: string,
      body?: object,
      onToken?: (content: string) => void
    ): Promise<{ data: T; fullContent: string }> => {
      // Cancel any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setIsStreaming(true);
      setStreamedContent('');

      const token = getAuthToken();
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const config = client.getConfig();
      const baseUrl = config.baseUrl || '';

      try {
        const response = await fetch(`${baseUrl}${url}`, {
          method: 'POST',
          headers,
          body: body ? JSON.stringify(body) : undefined,
          signal: abortController.signal,
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        let doneData: T | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const { events, remainder } = parseSSEEvents(buffer);
          buffer = remainder;

          for (const event of events) {
            if (event.event === 'token') {
              try {
                const tokenData = JSON.parse(event.data) as TokenEvent;
                fullContent += tokenData.content;
                setStreamedContent(fullContent);
                onToken?.(tokenData.content);
              } catch (e) {
                console.error('Failed to parse token event:', e);
              }
            } else if (event.event === 'done') {
              try {
                doneData = JSON.parse(event.data) as T;
              } catch (e) {
                // done event might have empty data
                doneData = {} as T;
              }
            }
          }
        }

        if (doneData === null) {
          throw new Error('Stream ended without done event');
        }

        return { data: doneData, fullContent };
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [getAuthToken]
  );

  /**
   * Start a new assessment attempt.
   *
   * Streams the orientation message and returns attempt metadata.
   */
  const startAssessment = useCallback(
    async (
      assignmentId: string,
      onToken?: (content: string) => void
    ): Promise<StartAssessmentResult> => {
      const { data, fullContent } = await streamPost<StartDoneEvent>(
        `/api/assessments/${assignmentId}/start`,
        undefined,
        onToken
      );

      return {
        attemptId: data.attempt_id,
        assignmentId: data.assignment_id,
        objectiveId: data.objective_id,
        objectiveTitle: data.objective_title,
        initialMessage: fullContent,
      };
    },
    [streamPost]
  );

  /**
   * Send a learner message and receive AI response.
   *
   * Streams the AI response.
   */
  const sendMessage = useCallback(
    async (
      attemptId: string,
      content: string,
      onToken?: (content: string) => void
    ): Promise<SendMessageResult> => {
      const { fullContent } = await streamPost<MessageDoneEvent>(
        `/api/assessments/${attemptId}/message`,
        { content },
        onToken
      );

      return {
        response: fullContent,
      };
    },
    [streamPost]
  );

  /**
   * Cancel any in-progress streaming request.
   */
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  return {
    startAssessment,
    sendMessage,
    cancelStream,
    isStreaming,
    streamedContent,
  };
}
