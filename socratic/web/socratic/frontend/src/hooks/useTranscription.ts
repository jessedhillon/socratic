/**
 * Hook for transcribing audio using the backend Whisper API.
 */

import { useCallback, useState } from 'react';
import { transcribeAudio } from '../api/sdk.gen';
import type { TranscriptionResponse } from '../api/types.gen';

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
        const response = await transcribeAudio({
          body: {
            file: new File([audioBlob], 'recording.webm', {
              type: audioBlob.type,
            }),
            language: options?.language ?? null,
          },
          throwOnError: true,
        });

        const data = response.data as TranscriptionResponse;
        const transcriptionResult: TranscriptionResult = {
          text: data.text,
          duration: data.duration ?? null,
          language: data.language ?? null,
        };

        setResult(transcriptionResult);
        setState('success');
        return transcriptionResult;
      } catch (err) {
        let message = 'Unknown error occurred';
        let code = 'api_error';

        if (err instanceof Error) {
          message = err.message;
        }

        // Check for HTTP error responses
        if (typeof err === 'object' && err !== null && 'status' in err) {
          const status = (err as { status: number }).status;
          if (status === 413) {
            code = 'file_too_large';
            message = 'File size exceeds maximum allowed';
          } else if (status === 415) {
            code = 'unsupported_format';
            message = 'Unsupported audio format';
          } else if (status === 401) {
            code = 'unauthorized';
            message = 'Not authenticated';
          }
        }

        setError({ message, code });
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
