import { useCallback, useRef, useState, useEffect } from 'react';
import { client } from '../../api/client.gen';
import { getAuthToken } from '../../auth';

/**
 * SSE event data types from the backend.
 */
interface TokenEvent {
  content: string;
}

/**
 * Data from the assessment_complete event.
 */
interface AssessmentCompleteEvent {
  evaluation_id?: string;
}

/**
 * Options for configuring the assessment API hook.
 */
export interface UseAssessmentApiOptions {
  /** Called when the backend signals assessment completion */
  onComplete?: (evaluationId?: string) => void;
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
 * Hook for consuming SSE streams from assessment endpoints.
 *
 * The backend uses a separate stream endpoint:
 * 1. POST /api/assessments/{assignment_id}/start - creates attempt, returns JSON
 * 2. GET /api/assessments/{attempt_id}/stream - SSE endpoint for events
 * 3. POST /api/assessments/{attempt_id}/message - sends message, returns 202
 *
 * Events are streamed via a persistent EventSource connection.
 */
export function useAssessmentApi(options: UseAssessmentApiOptions = {}) {
  const { onComplete } = options;

  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedContent, setStreamedContent] = useState('');
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  // Callback refs for handling events - these allow us to change handlers
  // without recreating the EventSource
  const tokenHandlerRef = useRef<((content: string) => void) | null>(null);
  const messageResolverRef = useRef<((content: string) => void) | null>(null);
  const messageRejecterRef = useRef<((error: Error) => void) | null>(null);
  const currentContentRef = useRef<string>('');

  // Store onComplete in a ref so it can be accessed in event handlers
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  /**
   * Ensure EventSource is connected for the given attempt.
   * Reuses existing connection if already connected to the same attempt.
   */
  const ensureConnected = useCallback((attemptId: string): EventSource => {
    const config = client.getConfig();
    const baseUrl = config.baseUrl || '';
    const token = getAuthToken();

    // Build URL with auth token and optional Last-Event-ID
    let streamUrl = `${baseUrl}/api/assessments/${attemptId}/stream`;
    const params = new URLSearchParams();
    if (token) {
      params.set('token', token);
    }
    if (lastEventIdRef.current) {
      params.set('lastEventId', lastEventIdRef.current);
    }
    if (params.toString()) {
      streamUrl += `?${params.toString()}`;
    }

    // Reuse existing connection if it's open and for the same URL pattern
    if (
      eventSourceRef.current &&
      eventSourceRef.current.readyState !== EventSource.CLOSED
    ) {
      return eventSourceRef.current;
    }

    // Create new EventSource
    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('token', (event) => {
      try {
        // Track the event ID for reconnection
        if (event.lastEventId) {
          lastEventIdRef.current = event.lastEventId;
        }

        const data = JSON.parse(event.data) as TokenEvent;
        currentContentRef.current += data.content;
        setStreamedContent(currentContentRef.current);
        tokenHandlerRef.current?.(data.content);
      } catch (e) {
        console.error('Failed to parse token event:', e);
      }
    });

    eventSource.addEventListener('message_done', (event) => {
      if (event.lastEventId) {
        lastEventIdRef.current = event.lastEventId;
      }
      setIsStreaming(false);
      // Resolve with the accumulated content
      const content = currentContentRef.current;
      messageResolverRef.current?.(content);
      // Clear handlers
      tokenHandlerRef.current = null;
      messageResolverRef.current = null;
      messageRejecterRef.current = null;
    });

    eventSource.addEventListener('error', () => {
      // EventSource auto-reconnects on transient errors
      // Only reject if we have no content and connection closed
      if (
        currentContentRef.current === '' &&
        eventSource.readyState === EventSource.CLOSED
      ) {
        setIsStreaming(false);
        messageRejecterRef.current?.(new Error('Stream connection failed'));
        tokenHandlerRef.current = null;
        messageResolverRef.current = null;
        messageRejecterRef.current = null;
      }
    });

    eventSource.addEventListener('assessment_complete', (event) => {
      if (event.lastEventId) {
        lastEventIdRef.current = event.lastEventId;
      }
      setIsStreaming(false);
      eventSource.close();
      eventSourceRef.current = null;

      // Parse event data and notify caller
      let evaluationId: string | undefined;
      try {
        const data = JSON.parse(event.data) as AssessmentCompleteEvent;
        evaluationId = data.evaluation_id;
      } catch {
        // Empty data is acceptable
      }
      onCompleteRef.current?.(evaluationId);
    });

    return eventSource;
  }, []);

  /**
   * Wait for the next message_done event.
   */
  const waitForMessage = useCallback(
    (
      attemptId: string,
      onToken?: (content: string) => void
    ): Promise<string> => {
      return new Promise((resolve, reject) => {
        // Reset content accumulator for this message
        currentContentRef.current = '';
        setStreamedContent('');
        setIsStreaming(true);

        // Set up handlers
        tokenHandlerRef.current = onToken || null;
        messageResolverRef.current = resolve;
        messageRejecterRef.current = reject;

        // Ensure connected
        ensureConnected(attemptId);
      });
    },
    [ensureConnected]
  );

  /**
   * Start a new assessment attempt.
   *
   * Calls POST /start to create the attempt, then connects to the stream
   * to receive the orientation message.
   */
  const startAssessment = useCallback(
    async (
      assignmentId: string,
      onToken?: (content: string) => void
    ): Promise<StartAssessmentResult> => {
      const config = client.getConfig();
      const baseUrl = config.baseUrl || '';
      const token = getAuthToken();

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // Reset last event ID for new assessment
      lastEventIdRef.current = null;

      // POST to start the assessment
      const response = await fetch(
        `${baseUrl}/api/assessments/${assignmentId}/start`,
        {
          method: 'POST',
          headers,
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      const attemptId = data.attempt_id;

      // Wait for the orientation message via stream
      const initialMessage = await waitForMessage(attemptId, onToken);

      return {
        attemptId,
        assignmentId: data.assignment_id,
        objectiveId: data.objective_id,
        objectiveTitle: data.objective_title,
        initialMessage,
      };
    },
    [waitForMessage]
  );

  /**
   * Send a learner message and receive AI response.
   *
   * Posts the message, then waits for the response via the persistent stream.
   */
  const sendMessage = useCallback(
    async (
      attemptId: string,
      content: string,
      onToken?: (content: string) => void
    ): Promise<SendMessageResult> => {
      const config = client.getConfig();
      const baseUrl = config.baseUrl || '';
      const token = getAuthToken();

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      // Set up to wait for response BEFORE posting (to not miss events)
      const messagePromise = waitForMessage(attemptId, onToken);

      // POST the message
      const response = await fetch(
        `${baseUrl}/api/assessments/${attemptId}/message`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({ content }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      // Wait for the AI response via stream
      const responseContent = await messagePromise;

      return {
        response: responseContent,
      };
    },
    [waitForMessage]
  );

  /**
   * Cancel any in-progress streaming request.
   */
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    tokenHandlerRef.current = null;
    messageResolverRef.current = null;
    messageRejecterRef.current = null;
    lastEventIdRef.current = null;
    setIsStreaming(false);
  }, []);

  return {
    startAssessment,
    sendMessage,
    cancelStream,
    isStreaming,
    streamedContent,
  };
}
