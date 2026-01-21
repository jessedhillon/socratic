import { useCallback, useMemo, useRef, useState } from 'react';

/**
 * Recording state for the MediaRecorder hook.
 */
export type RecordingState =
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'paused'
  | 'stopped'
  | 'error';

/**
 * Error types that can occur during recording.
 */
export type RecordingError =
  | { type: 'not_supported'; message: string }
  | { type: 'permission_denied'; message: string }
  | { type: 'no_device'; message: string }
  | { type: 'recorder_error'; message: string };

/**
 * Options for configuring the MediaRecorder.
 */
export interface MediaRecorderOptions {
  /** Video constraints for getUserMedia */
  video?: boolean | MediaTrackConstraints;
  /** Audio constraints for getUserMedia */
  audio?: boolean | MediaTrackConstraints;
  /** Preferred MIME type (e.g., 'video/webm;codecs=vp8,opus') */
  mimeType?: string;
  /** Interval in ms to fire ondataavailable (default: 1000) */
  timeslice?: number;
  /** Video bits per second (default: 2500000 for 2.5 Mbps) */
  videoBitsPerSecond?: number;
  /** Audio bits per second (default: 128000 for 128 kbps) */
  audioBitsPerSecond?: number;
}

/**
 * Result from the useMediaRecorder hook.
 */
export interface UseMediaRecorderResult {
  /** Current recording state */
  state: RecordingState;
  /** Error if state is 'error' */
  error: RecordingError | null;
  /** The media stream (available after start) */
  stream: MediaStream | null;
  /** Recorded chunks (available during and after recording) */
  chunks: Blob[];
  /** Duration in seconds */
  duration: number;
  /** Request permissions and start recording */
  start: () => Promise<void>;
  /** Stop recording and finalize */
  stop: () => Promise<Blob | null>;
  /** Pause recording */
  pause: () => void;
  /** Resume recording */
  resume: () => void;
  /** Clear recorded data and reset state */
  reset: () => void;
  /** Check if MediaRecorder is supported */
  isSupported: boolean;
  /** Get the final blob (call after stop) */
  getBlob: () => Blob | null;
}

/**
 * Default options for MediaRecorder.
 */
const DEFAULT_OPTIONS: Required<MediaRecorderOptions> = {
  video: true,
  audio: true,
  mimeType: '',
  timeslice: 1000,
  videoBitsPerSecond: 2500000,
  audioBitsPerSecond: 128000,
};

/**
 * Get the best supported MIME type for video recording.
 */
function getSupportedMimeType(): string {
  const types = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
    'video/mp4',
  ];

  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }

  return '';
}

/**
 * Check if MediaRecorder API is supported in the current browser.
 */
function isMediaRecorderSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'MediaRecorder' in window &&
    'getUserMedia' in navigator.mediaDevices
  );
}

/**
 * Hook for recording video/audio using the MediaRecorder API.
 *
 * Handles the full lifecycle: permission request, recording, chunk collection,
 * and blob assembly. Supports pause/resume and provides error handling for
 * unsupported browsers and permission issues.
 *
 * @example
 * ```tsx
 * function VideoRecorder() {
 *   const { state, start, stop, stream, error } = useMediaRecorder({
 *     video: true,
 *     audio: true,
 *   });
 *
 *   return (
 *     <div>
 *       {stream && <video srcObject={stream} autoPlay muted />}
 *       {state === 'idle' && <button onClick={start}>Start</button>}
 *       {state === 'recording' && <button onClick={stop}>Stop</button>}
 *       {error && <p>Error: {error.message}</p>}
 *     </div>
 *   );
 * }
 * ```
 */
export function useMediaRecorder(
  options: MediaRecorderOptions = {}
): UseMediaRecorderResult {
  const {
    video = DEFAULT_OPTIONS.video,
    audio = DEFAULT_OPTIONS.audio,
    mimeType = DEFAULT_OPTIONS.mimeType,
    timeslice = DEFAULT_OPTIONS.timeslice,
    videoBitsPerSecond = DEFAULT_OPTIONS.videoBitsPerSecond,
    audioBitsPerSecond = DEFAULT_OPTIONS.audioBitsPerSecond,
  } = options;

  const opts = useMemo(
    () => ({
      video,
      audio,
      mimeType,
      timeslice,
      videoBitsPerSecond,
      audioBitsPerSecond,
    }),
    [video, audio, mimeType, timeslice, videoBitsPerSecond, audioBitsPerSecond]
  );

  const [state, setState] = useState<RecordingState>('idle');
  const [error, setError] = useState<RecordingError | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [chunks, setChunks] = useState<Blob[]>([]);
  const [duration, setDuration] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const accumulatedDurationRef = useRef<number>(0);
  const durationIntervalRef = useRef<number | null>(null);
  const finalBlobRef = useRef<Blob | null>(null);

  const isSupported = isMediaRecorderSupported();

  /**
   * Start duration tracking interval.
   * @param fromResume - If true, continues from accumulated duration instead of resetting
   */
  const startDurationTracking = useCallback((fromResume: boolean = false) => {
    startTimeRef.current = Date.now();
    if (!fromResume) {
      accumulatedDurationRef.current = 0;
    }
    durationIntervalRef.current = window.setInterval(() => {
      const currentSegment = Math.floor(
        (Date.now() - startTimeRef.current) / 1000
      );
      setDuration(accumulatedDurationRef.current + currentSegment);
    }, 1000);
  }, []);

  /**
   * Stop duration tracking interval.
   * @param saveAccumulated - If true, saves current duration to accumulated for resume
   */
  const stopDurationTracking = useCallback(
    (saveAccumulated: boolean = false) => {
      if (durationIntervalRef.current !== null) {
        if (saveAccumulated) {
          // Save the current total duration for resuming later
          const currentSegment = Math.floor(
            (Date.now() - startTimeRef.current) / 1000
          );
          accumulatedDurationRef.current += currentSegment;
        }
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
    },
    []
  );

  /**
   * Clean up media resources.
   */
  const cleanup = useCallback(() => {
    stopDurationTracking();

    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      mediaRecorderRef.current = null;
    }

    // Use ref to avoid stale closure over stream state
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setStream(null);
    }
  }, [stopDurationTracking]);

  /**
   * Request permissions and start recording.
   */
  const start = useCallback(async () => {
    if (!isSupported) {
      setError({
        type: 'not_supported',
        message: 'MediaRecorder is not supported in this browser',
      });
      setState('error');
      return;
    }

    setState('requesting');
    setError(null);
    chunksRef.current = [];
    setChunks([]);
    finalBlobRef.current = null;
    setDuration(0);

    try {
      // Request media stream
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: opts.video,
        audio: opts.audio,
      });

      streamRef.current = mediaStream;
      setStream(mediaStream);

      // Determine MIME type
      const mimeType = opts.mimeType || getSupportedMimeType();

      // Create MediaRecorder
      const recorderOptions: MediaRecorderOptions = {
        videoBitsPerSecond: opts.videoBitsPerSecond,
        audioBitsPerSecond: opts.audioBitsPerSecond,
      };

      if (mimeType) {
        recorderOptions.mimeType = mimeType;
      }

      const recorder = new MediaRecorder(mediaStream, recorderOptions);
      mediaRecorderRef.current = recorder;

      // Handle data availability
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
          setChunks([...chunksRef.current]);
        }
      };

      // Handle errors
      recorder.onerror = (event) => {
        console.error('MediaRecorder error:', event);
        setError({
          type: 'recorder_error',
          message: 'An error occurred during recording',
        });
        setState('error');
        cleanup();
      };

      // Handle stop
      recorder.onstop = () => {
        // Assemble final blob
        if (chunksRef.current.length > 0) {
          const blobType = mimeType || 'video/webm';
          finalBlobRef.current = new Blob(chunksRef.current, {
            type: blobType,
          });
        }
      };

      // Start recording with timeslice
      recorder.start(opts.timeslice);
      setState('recording');
      startDurationTracking();
    } catch (err) {
      console.error('Failed to start recording:', err);

      if (err instanceof DOMException) {
        if (err.name === 'NotAllowedError') {
          setError({
            type: 'permission_denied',
            message: 'Camera/microphone permission was denied',
          });
        } else if (err.name === 'NotFoundError') {
          setError({
            type: 'no_device',
            message: 'No camera or microphone found',
          });
        } else {
          setError({
            type: 'recorder_error',
            message: err.message,
          });
        }
      } else {
        setError({
          type: 'recorder_error',
          message: err instanceof Error ? err.message : 'Unknown error',
        });
      }

      setState('error');
      cleanup();
    }
  }, [isSupported, opts, cleanup, startDurationTracking]);

  /**
   * Stop recording and finalize.
   */
  const stop = useCallback(async (): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;

      if (!recorder || recorder.state === 'inactive') {
        setState('stopped');
        cleanup();
        resolve(finalBlobRef.current);
        return;
      }

      // Wait for the final chunk
      const originalOnStop = recorder.onstop;
      recorder.onstop = (event) => {
        originalOnStop?.call(recorder, event);
        setState('stopped');
        stopDurationTracking();

        // Stop all tracks - use ref to avoid stale closure
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
          setStream(null);
        }

        resolve(finalBlobRef.current);
      };

      recorder.stop();
    });
  }, [cleanup, stopDurationTracking]);

  /**
   * Pause recording.
   */
  const pause = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === 'recording') {
      recorder.pause();
      setState('paused');
      stopDurationTracking(true); // Save accumulated duration for resume
    }
  }, [stopDurationTracking]);

  /**
   * Resume recording.
   */
  const resume = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === 'paused') {
      recorder.resume();
      setState('recording');
      startDurationTracking(true); // Continue from accumulated duration
    }
  }, [startDurationTracking]);

  /**
   * Reset state and clear recorded data.
   */
  const reset = useCallback(() => {
    cleanup();
    setState('idle');
    setError(null);
    setChunks([]);
    chunksRef.current = [];
    finalBlobRef.current = null;
    accumulatedDurationRef.current = 0;
    setDuration(0);
  }, [cleanup]);

  /**
   * Get the final assembled blob.
   */
  const getBlob = useCallback((): Blob | null => {
    if (finalBlobRef.current) {
      return finalBlobRef.current;
    }

    // Assemble from chunks if not yet assembled
    if (chunksRef.current.length > 0) {
      const mimeType = opts.mimeType || getSupportedMimeType() || 'video/webm';
      return new Blob(chunksRef.current, { type: mimeType });
    }

    return null;
  }, [opts.mimeType]);

  return {
    state,
    error,
    stream,
    chunks,
    duration,
    start,
    stop,
    pause,
    resume,
    reset,
    isSupported,
    getBlob,
  };
}
