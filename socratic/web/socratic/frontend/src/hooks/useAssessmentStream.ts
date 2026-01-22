/**
 * Low-level hook for assessment EventSource streaming.
 *
 * This hook provides explicit control over the SSE connection lifecycle,
 * useful for debugging and development tools. For production assessment
 * flows, use the higher-level useAssessmentStream from components/assessment.
 *
 * Uses native EventSource for SSE streaming which provides:
 * - Automatic reconnection with Last-Event-ID
 * - Built-in SSE parsing
 * - Clean browser-native implementation
 */

import { useCallback, useRef, useState, useEffect } from 'react';
import {
  startAssessment as startAssessmentApi,
  sendAssessmentMessage as sendMessageApi,
  completeAssessment as completeAssessmentApi,
} from '../api/sdk.gen';
import { getAuthToken } from '../auth';
import type {
  StartAssessmentOkResponse,
  CompleteAssessmentOkResponse,
} from '../api/types.gen';

/** Response from sending a message - defined locally as API types it as unknown */
interface MessageAcceptedResponse {
  message_id: string;
}

/** Extract error message from API error detail which can be string or ValidationError[] */
function getErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    // ValidationError format: { loc: string[], msg: string, type: string }
    const firstError = detail[0];
    if (typeof firstError?.msg === 'string') {
      return firstError.msg;
    }
  }
  return fallback;
}

/** Callbacks for handling stream events */
export interface StreamCallbacks {
  /** Called for each token in the AI response */
  onToken: (content: string) => void;
  /** Called when a complete message has been delivered */
  onMessageDone: () => void;
  /** Called when the assessment is complete */
  onComplete: (evaluationId?: string) => void;
  /** Called on stream errors */
  onError: (message: string, recoverable: boolean) => void;
}

/** Connection state for the EventSource */
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error';

export interface UseAssessmentStreamResult {
  /** Start a new assessment attempt */
  startAssessment: (assignmentId: string) => Promise<StartAssessmentOkResponse>;

  /**
   * Connect to the event stream for an attempt.
   * Call this after startAssessment to receive streaming events.
   */
  connectStream: (attemptId: string, callbacks: StreamCallbacks) => void;

  /**
   * Send a learner message.
   * The response will be streamed via the connected EventSource.
   */
  sendMessage: (
    attemptId: string,
    content: string
  ) => Promise<MessageAcceptedResponse>;

  /**
   * Complete the assessment.
   * This will trigger the assessment_complete event on the stream.
   */
  completeAssessment: (
    attemptId: string,
    feedback?: string
  ) => Promise<CompleteAssessmentOkResponse>;

  /** Disconnect from the event stream */
  disconnect: () => void;

  /** Current connection state */
  connectionState: ConnectionState;
}

/**
 * Hook for managing assessment API interactions with EventSource streaming.
 *
 * @example
 * ```tsx
 * const { startAssessment, connectStream, sendMessage, connectionState } = useAssessmentStream();
 *
 * const handleStart = async () => {
 *   const { attempt_id, objective_title } = await startAssessment(assignmentId);
 *
 *   connectStream(attempt_id, {
 *     onToken: (content) => appendToMessage(content),
 *     onMessageDone: () => finalizeMessage(),
 *     onComplete: () => showResults(),
 *     onError: (msg, recoverable) => handleError(msg, recoverable),
 *   });
 * };
 * ```
 */
export function useAssessmentStream(): UseAssessmentStreamResult {
  const eventSourceRef = useRef<EventSource | null>(null);
  const callbacksRef = useRef<StreamCallbacks | null>(null);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('disconnected');

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const startAssessment = useCallback(
    async (assignmentId: string): Promise<StartAssessmentOkResponse> => {
      const response = await startAssessmentApi({
        path: { assignment_id: assignmentId },
      });

      if (response.error) {
        throw new Error(
          getErrorMessage(response.error.detail, 'Failed to start assessment')
        );
      }

      return response.data;
    },
    []
  );

  const connectStream = useCallback(
    (attemptId: string, callbacks: StreamCallbacks) => {
      // Close existing connection if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      callbacksRef.current = callbacks;
      setConnectionState('connecting');

      // EventSource doesn't support custom headers, so we pass the token as a query param
      const token = getAuthToken();
      const url = token
        ? `/api/assessments/${attemptId}/stream?token=${encodeURIComponent(token)}`
        : `/api/assessments/${attemptId}/stream`;

      const es = new EventSource(url, {
        withCredentials: true,
      });

      es.onopen = () => {
        setConnectionState('connected');
      };

      es.onerror = () => {
        // EventSource fires 'error' for both connection issues and server errors
        // Check readyState to understand the situation
        if (es.readyState === EventSource.CLOSED) {
          setConnectionState('disconnected');
        } else if (es.readyState === EventSource.CONNECTING) {
          // Automatic reconnection in progress
          setConnectionState('connecting');
        } else {
          setConnectionState('error');
        }
      };

      // Handle token events
      es.addEventListener('token', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          callbacksRef.current?.onToken(data.content);
        } catch {
          console.error('Failed to parse token event:', event.data);
        }
      });

      // Handle message completion
      es.addEventListener('message_done', () => {
        callbacksRef.current?.onMessageDone();
      });

      // Handle assessment completion
      es.addEventListener('assessment_complete', (event: MessageEvent) => {
        let evaluationId: string | undefined;
        try {
          const data = JSON.parse(event.data);
          evaluationId = data.evaluation_id;
        } catch {
          // Empty data is fine
        }
        callbacksRef.current?.onComplete(evaluationId);
        es.close();
        setConnectionState('disconnected');
      });

      // Handle error events from the server
      es.addEventListener('error', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          callbacksRef.current?.onError(
            data.message,
            data.recoverable ?? false
          );
        } catch {
          callbacksRef.current?.onError('Unknown error occurred', false);
        }
      });

      eventSourceRef.current = es;
    },
    []
  );

  const sendMessage = useCallback(
    async (
      attemptId: string,
      content: string
    ): Promise<MessageAcceptedResponse> => {
      const response = await sendMessageApi({
        path: { attempt_id: attemptId },
        body: { content },
      });

      if (response.error) {
        throw new Error(
          getErrorMessage(response.error.detail, 'Failed to send message')
        );
      }

      // Cast response.data since the API types it as unknown
      return response.data as MessageAcceptedResponse;
    },
    []
  );

  const completeAssessment = useCallback(
    async (
      attemptId: string,
      feedback?: string
    ): Promise<CompleteAssessmentOkResponse> => {
      const response = await completeAssessmentApi({
        path: { attempt_id: attemptId },
        body: { feedback: feedback ?? null },
      });

      if (response.error) {
        throw new Error(
          getErrorMessage(
            response.error.detail,
            'Failed to complete assessment'
          )
        );
      }

      return response.data;
    },
    []
  );

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    callbacksRef.current = null;
    setConnectionState('disconnected');
  }, []);

  return {
    startAssessment,
    connectStream,
    sendMessage,
    completeAssessment,
    disconnect,
    connectionState,
  };
}

export default useAssessmentStream;
