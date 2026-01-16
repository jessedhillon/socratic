/**
 * Hook for transcribing audio using the backend Whisper API.
 */

import { useCallback, useState } from 'react';
import { getAuthToken } from '../auth';

/** State of the transcription process */
export type TranscriptionState = 'idle' | 'transcribing' | 'success' | 'error';

/** Result from successful transcription */
export interface TranscriptionResult {
  text: string;
  duration: number | null;
  language: string | null;
}

/** Error from transcription */
export interface TranscriptionError {
  message: string;
  code: string;
}

/** Options for transcription */
export interface TranscribeOptions {
  /** ISO language code to hint to Whisper (e.g., 'en', 'es') */
  language?: string;
}

export interface UseTranscriptionResult {
  /** Current state of transcription */
  state: TranscriptionState;
  /** Result from last successful transcription */
  result: TranscriptionResult | null;
  /** Error from last failed transcription */
  error: TranscriptionError | null;
  /** Transcribe an audio blob */
  transcribe: (
    audioBlob: Blob,
    options?: TranscribeOptions
  ) => Promise<TranscriptionResult | null>;
  /** Reset state to idle */
  reset: () => void;
}

/**
 * Hook for transcribing audio blobs to text using OpenAI Whisper.
 *
 * @example
 * ```tsx
 * const { state, result, error, transcribe, reset } = useTranscription();
 *
 * const handleRecordingComplete = async (audioBlob: Blob) => {
 *   const result = await transcribe(audioBlob);
 *   if (result) {
 *     console.log('Transcribed:', result.text);
 *   }
 * };
 * ```
 */
export function useTranscription(): UseTranscriptionResult {
  const [state, setState] = useState<TranscriptionState>('idle');
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [error, setError] = useState<TranscriptionError | null>(null);

  const transcribe = useCallback(
    async (
      audioBlob: Blob,
      options?: TranscribeOptions
    ): Promise<TranscriptionResult | null> => {
      setState('transcribing');
      setError(null);

      try {
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');

        if (options?.language) {
          formData.append('language', options.language);
        }

        const token = getAuthToken();
        const headers: HeadersInit = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch('/api/transcription', {
          method: 'POST',
          headers,
          body: formData,
        });

        if (!response.ok) {
          let errorData: { error?: string; detail?: string } = {};
          try {
            errorData = await response.json();
          } catch {
            // Response may not be JSON
          }

          const errorMessage =
            errorData.error || errorData.detail || `HTTP ${response.status}`;
          const errorCode =
            response.status === 413
              ? 'file_too_large'
              : response.status === 415
                ? 'unsupported_format'
                : 'api_error';

          setError({ message: errorMessage, code: errorCode });
          setState('error');
          return null;
        }

        const data = await response.json();
        const transcriptionResult: TranscriptionResult = {
          text: data.text,
          duration: data.duration ?? null,
          language: data.language ?? null,
        };

        setResult(transcriptionResult);
        setState('success');
        return transcriptionResult;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Unknown error occurred';
        setError({ message, code: 'network_error' });
        setState('error');
        return null;
      }
    },
    []
  );

  const reset = useCallback(() => {
    setState('idle');
    setResult(null);
    setError(null);
  }, []);

  return {
    state,
    result,
    error,
    transcribe,
    reset,
  };
}

export default useTranscription;
