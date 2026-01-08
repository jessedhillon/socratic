import { useState, useCallback } from 'react';

interface SSEOptions {
  onToken?: (token: string) => void;
  onDone?: (data: unknown) => void;
  onError?: (error: Error) => void;
}

interface SSEState {
  isStreaming: boolean;
  error: Error | null;
}

/**
 * Hook for handling Server-Sent Events streaming responses.
 * Used for real-time AI message streaming during assessments.
 */
export function useSSE() {
  const [state, setState] = useState<SSEState>({
    isStreaming: false,
    error: null,
  });

  const stream = useCallback(
    async (
      url: string,
      options: {
        method?: 'GET' | 'POST';
        body?: unknown;
        headers?: Record<string, string>;
      } & SSEOptions
    ): Promise<void> => {
      const {
        method = 'POST',
        body,
        headers = {},
        onToken,
        onDone,
        onError,
      } = options;

      setState({ isStreaming: true, error: null });

      try {
        const response = await fetch(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
            ...headers,
          },
          body: body ? JSON.stringify(body) : undefined,
          credentials: 'include',
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              // Store event type for next data line
              continue;
            }
            if (line.startsWith('data:')) {
              const data = line.slice(5).trim();
              if (!data) continue;

              try {
                const parsed = JSON.parse(data);
                if ('content' in parsed && onToken) {
                  onToken(parsed.content);
                } else if (onDone) {
                  onDone(parsed);
                }
              } catch {
                // If it's not JSON, it might be the "done" event with empty data
                if (data === '' && onDone) {
                  onDone(null);
                }
              }
            }
          }
        }

        setState({ isStreaming: false, error: null });
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error));
        setState({ isStreaming: false, error: err });
        onError?.(err);
      }
    },
    []
  );

  return {
    ...state,
    stream,
  };
}

export default useSSE;
