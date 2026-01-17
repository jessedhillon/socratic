/**
 * Hook for text-to-speech synthesis using the backend TTS API.
 */

import { useState, useCallback, useRef } from 'react';
import { synthesizeSpeech } from '../api/sdk.gen';

export type Voice = 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';
export type SpeechFormat = 'mp3' | 'opus' | 'aac' | 'flac' | 'wav' | 'pcm';

export interface SpeechOptions {
  /** Voice to use for synthesis */
  voice?: Voice;
  /** Output audio format */
  format?: SpeechFormat;
  /** Speech speed (0.25-4.0) */
  speed?: number;
}

export interface SpeechState {
  /** Whether speech synthesis is in progress */
  isLoading: boolean;
  /** Whether audio is currently playing */
  isPlaying: boolean;
  /** Error message if synthesis or playback failed */
  error: string | null;
}

export interface UseSpeechResult {
  /** Current state of speech synthesis and playback */
  state: SpeechState;
  /** Synthesize speech from text and optionally play it */
  speak: (
    text: string,
    options?: SpeechOptions & { autoPlay?: boolean }
  ) => Promise<Blob>;
  /** Play previously synthesized audio */
  play: (audioBlob: Blob) => Promise<void>;
  /** Stop any currently playing audio */
  stop: () => void;
  /** Reset error state */
  clearError: () => void;
}

/**
 * Hook for converting text to speech and playing the result.
 *
 * @example
 * ```tsx
 * const { state, speak, stop } = useSpeech();
 *
 * // Synthesize and play immediately
 * await speak("Hello, world!", { autoPlay: true });
 *
 * // Or synthesize first, play later
 * const audioBlob = await speak("Hello, world!");
 * await play(audioBlob);
 *
 * // Stop playback
 * stop();
 * ```
 */
export function useSpeech(): UseSpeechResult {
  const [state, setState] = useState<SpeechState>({
    isLoading: false,
    isPlaying: false,
    error: null,
  });

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  const speak = useCallback(
    async (
      text: string,
      options: SpeechOptions & { autoPlay?: boolean } = {}
    ): Promise<Blob> => {
      const {
        voice = 'nova',
        format = 'mp3',
        speed = 1.0,
        autoPlay = false,
      } = options;

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const response = await synthesizeSpeech({
          body: {
            text,
            voice,
            format,
            speed,
          },
          parseAs: 'blob',
          throwOnError: true,
        });

        const audioBlob = response.data as Blob;

        setState((prev) => ({ ...prev, isLoading: false }));

        if (autoPlay) {
          await playAudio(audioBlob);
        }

        return audioBlob;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Speech synthesis failed';
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: errorMessage,
        }));
        throw err;
      }
    },
    []
  );

  const playAudio = useCallback(
    async (audioBlob: Blob): Promise<void> => {
      // Clean up any existing audio
      cleanupAudio();

      return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(audioBlob);
        audioUrlRef.current = url;

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onplay = () => {
          setState((prev) => ({ ...prev, isPlaying: true }));
        };

        audio.onended = () => {
          setState((prev) => ({ ...prev, isPlaying: false }));
          cleanupAudio();
          resolve();
        };

        audio.onerror = () => {
          setState((prev) => ({
            ...prev,
            isPlaying: false,
            error: 'Audio playback failed',
          }));
          cleanupAudio();
          reject(new Error('Audio playback failed'));
        };

        audio.play().catch((err) => {
          setState((prev) => ({
            ...prev,
            isPlaying: false,
            error: 'Could not start playback',
          }));
          cleanupAudio();
          reject(err);
        });
      });
    },
    [cleanupAudio]
  );

  const stop = useCallback(() => {
    cleanupAudio();
    setState((prev) => ({ ...prev, isPlaying: false }));
  }, [cleanupAudio]);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    state,
    speak,
    play: playAudio,
    stop,
    clearError,
  };
}
