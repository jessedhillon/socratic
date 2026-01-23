/**
 * Hook for mixing multiple audio sources (microphone + TTS) into a single
 * recordable stream using the Web Audio API.
 *
 * This enables recording both the learner's voice and the AI's TTS responses
 * in a single video file.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

export interface AudioMixerState {
  /** Whether the mixer is initialized and ready */
  isReady: boolean;
  /** Whether audio is currently playing through the mixer */
  isPlaying: boolean;
  /** Duration of the currently playing audio in seconds */
  duration: number | null;
  /** Error message if initialization or playback failed */
  error: string | null;
}

export interface UseAudioMixerResult {
  /** Current state of the audio mixer */
  state: AudioMixerState;
  /** Initialize the mixer with a microphone stream */
  initialize: (micStream: MediaStream) => Promise<MediaStream>;
  /** Play an audio blob through the mixer (also outputs to speakers) */
  playAudio: (audioBlob: Blob) => Promise<void>;
  /** Stop any currently playing audio */
  stopAudio: () => void;
  /** Clean up all resources */
  cleanup: () => void;
  /** The mixed output stream (mic + TTS) for recording */
  mixedStream: MediaStream | null;
}

/**
 * Hook for mixing microphone input with TTS audio output.
 *
 * The mixed stream can be used with MediaRecorder to capture both sides
 * of the conversation in a single recording.
 *
 * @example
 * ```tsx
 * const { initialize, playAudio, mixedStream } = useAudioMixer();
 *
 * // Initialize with mic stream
 * const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
 * const mixedStream = await initialize(micStream);
 *
 * // Use mixedStream for MediaRecorder
 * const recorder = new MediaRecorder(new MediaStream([
 *   ...videoTrack,
 *   ...mixedStream.getAudioTracks()
 * ]));
 *
 * // Play TTS through mixer (also plays to speakers)
 * await playAudio(ttsBlob);
 * ```
 */
export function useAudioMixer(): UseAudioMixerResult {
  const [state, setState] = useState<AudioMixerState>({
    isReady: false,
    isPlaying: false,
    duration: null,
    error: null,
  });

  const [mixedStream, setMixedStream] = useState<MediaStream | null>(null);

  // Refs for Web Audio API objects
  const audioContextRef = useRef<AudioContext | null>(null);
  const destinationRef = useRef<MediaStreamAudioDestinationNode | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micGainRef = useRef<GainNode | null>(null);
  const ttsGainRef = useRef<GainNode | null>(null);

  // Ref for current audio element (for TTS playback)
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const audioSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  /**
   * Initialize the audio mixer with a microphone stream.
   * Returns the mixed output stream for recording.
   */
  const initialize = useCallback(
    async (micStream: MediaStream): Promise<MediaStream> => {
      try {
        // Create AudioContext
        const audioContext = new AudioContext();
        audioContextRef.current = audioContext;

        // Resume context if suspended (required after user gesture)
        if (audioContext.state === 'suspended') {
          await audioContext.resume();
        }

        // Create destination for recording
        const destination = audioContext.createMediaStreamDestination();
        destinationRef.current = destination;

        // Create gain nodes for level control
        const micGain = audioContext.createGain();
        micGain.gain.value = 1.0; // Full mic volume
        micGainRef.current = micGain;

        const ttsGain = audioContext.createGain();
        ttsGain.gain.value = 1.0; // Full TTS volume
        ttsGainRef.current = ttsGain;

        // Connect microphone to destination (for recording)
        const micSource = audioContext.createMediaStreamSource(micStream);
        micSourceRef.current = micSource;
        micSource.connect(micGain);
        micGain.connect(destination);

        // TTS will be connected when playAudio is called
        // Connect TTS gain to both destination (recording) and speakers
        ttsGain.connect(destination);
        ttsGain.connect(audioContext.destination);

        setMixedStream(destination.stream);
        setState((prev) => ({ ...prev, isReady: true, error: null }));

        return destination.stream;
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : 'Failed to initialize audio mixer';
        setState((prev) => ({ ...prev, error: errorMessage }));
        throw err;
      }
    },
    []
  );

  /**
   * Play an audio blob through the mixer.
   * Audio plays through speakers AND is mixed into the recording stream.
   */
  const playAudio = useCallback(async (audioBlob: Blob): Promise<void> => {
    const audioContext = audioContextRef.current;
    const ttsGain = ttsGainRef.current;

    if (!audioContext || !ttsGain) {
      throw new Error('Audio mixer not initialized');
    }

    // Resume context if suspended
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    // Clean up previous audio
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.src = '';
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
    }
    // Note: We don't disconnect audioSourceRef because createMediaElementSource
    // can only be called once per element. Instead, we reuse or create new.

    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(audioBlob);
      audioUrlRef.current = url;

      const audio = new Audio();
      audio.src = url;
      audioElementRef.current = audio;

      // Create media element source and connect to TTS gain
      // This routes the audio through our mixer
      const source = audioContext.createMediaElementSource(audio);
      audioSourceRef.current = source;
      source.connect(ttsGain);

      // Get duration when metadata loads, then start playback
      audio.onloadedmetadata = () => {
        const duration = audio.duration;
        setState((prev) => ({ ...prev, duration }));

        // Now start playback
        audio.play().catch((err) => {
          setState((prev) => ({
            ...prev,
            isPlaying: false,
            error: 'Could not start playback',
          }));
          reject(err);
        });
      };

      audio.onplay = () => {
        setState((prev) => ({ ...prev, isPlaying: true }));
      };

      audio.onended = () => {
        setState((prev) => ({ ...prev, isPlaying: false, duration: null }));
        resolve();
      };

      audio.onerror = () => {
        setState((prev) => ({
          ...prev,
          isPlaying: false,
          duration: null,
          error: 'Audio playback failed',
        }));
        reject(new Error('Audio playback failed'));
      };

      // Trigger loading
      audio.load();
    });
  }, []);

  /**
   * Stop any currently playing audio.
   */
  const stopAudio = useCallback(() => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
    }
    setState((prev) => ({ ...prev, isPlaying: false }));
  }, []);

  /**
   * Clean up all audio resources.
   */
  const cleanup = useCallback(() => {
    // Stop and clean up audio element
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.src = '';
      audioElementRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }

    // Disconnect nodes
    if (micSourceRef.current) {
      micSourceRef.current.disconnect();
      micSourceRef.current = null;
    }
    if (audioSourceRef.current) {
      audioSourceRef.current.disconnect();
      audioSourceRef.current = null;
    }
    if (micGainRef.current) {
      micGainRef.current.disconnect();
      micGainRef.current = null;
    }
    if (ttsGainRef.current) {
      ttsGainRef.current.disconnect();
      ttsGainRef.current = null;
    }
    if (destinationRef.current) {
      destinationRef.current.disconnect();
      destinationRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    setMixedStream(null);
    setState({ isReady: false, isPlaying: false, duration: null, error: null });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    state,
    initialize,
    playAudio,
    stopAudio,
    cleanup,
    mixedStream,
  };
}

export default useAudioMixer;
