import { useCallback, useEffect, useRef, useState } from 'react';
import {
  useMediaRecorder,
  RecordingState,
  RecordingError,
} from './useMediaRecorder';

/**
 * Helper hook to keep a ref updated with the latest value.
 * Useful for accessing current values in event handlers without stale closures.
 */
function useLatest<T>(value: T): React.MutableRefObject<T> {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}

/**
 * Session state for the recording lifecycle.
 */
export type SessionState =
  | 'idle'
  | 'initializing'
  | 'ready'
  | 'recording'
  | 'paused'
  | 'stopping'
  | 'completed'
  | 'error'
  | 'abandoned';

/**
 * Options for configuring the recording session.
 */
export interface RecordingSessionOptions {
  /** Whether to pause recording when tab is hidden (default: true) */
  pauseOnHidden?: boolean;
  /** Whether to auto-start recording after permissions are granted */
  autoStart?: boolean;
  /** Maximum recording duration in seconds (0 = unlimited) */
  maxDuration?: number;
  /** Interval in ms between chunk uploads (default: 10000 for 10 seconds, 0 = disabled) */
  chunkUploadIntervalMs?: number;
  /**
   * Optional externally-provided media stream to use instead of calling getUserMedia.
   * When provided, the hook will use this stream for preview/visualization.
   */
  externalStream?: MediaStream | null;
  /**
   * Optional mixed audio stream to use for recording instead of the raw mic audio.
   * When provided, the recording will use audio from this stream (e.g., mic + TTS mixed)
   * while the original stream remains available for preview/visualization.
   */
  mixedAudioStream?: MediaStream | null;
  /** Callback when recording starts */
  onStart?: () => void;
  /** Callback when recording is paused */
  onPause?: () => void;
  /** Callback when recording is resumed */
  onResume?: () => void;
  /** Callback when recording stops with final blob */
  onStop?: (blob: Blob | null) => void;
  /** Callback on recording error */
  onError?: (error: RecordingError) => void;
  /** Callback when max duration is reached */
  onMaxDurationReached?: () => void;
  /** Callback when a chunk is ready for upload (progressive upload) */
  onChunkReady?: (chunk: Blob, sequence: number) => void;
}

/**
 * Result from the useRecordingSession hook.
 */
export interface UseRecordingSessionResult {
  /** Current session state */
  sessionState: SessionState;
  /** Current recording state from MediaRecorder */
  recordingState: RecordingState;
  /** Recording error if any */
  error: RecordingError | null;
  /** The media stream */
  stream: MediaStream | null;
  /** Current recording duration in seconds */
  duration: number;
  /** Whether recording is currently active (recording or paused) */
  isActive: boolean;
  /** Whether recording was paused due to tab being hidden */
  isPausedByVisibility: boolean;
  /** Initialize the session (request permissions) */
  initialize: () => Promise<boolean>;
  /** Start recording */
  startRecording: () => Promise<void>;
  /** Stop recording and get final blob */
  stopRecording: () => Promise<Blob | null>;
  /** Pause recording */
  pauseRecording: () => void;
  /** Resume recording */
  resumeRecording: () => void;
  /** Abandon the session (cleanup without completing) */
  abandon: () => void;
  /** Reset to initial state */
  reset: () => void;
}

/**
 * Hook for managing the full lifecycle of video recording during an assessment.
 *
 * Features:
 * - Automatic pause/resume on tab visibility changes
 * - Error recovery and cleanup
 * - Max duration enforcement
 * - Integration points for assessment state machine
 * - Memory-efficient chunk handling
 *
 * @example
 * ```tsx
 * function AssessmentRecorder() {
 *   const {
 *     sessionState,
 *     stream,
 *     duration,
 *     initialize,
 *     startRecording,
 *     stopRecording,
 *   } = useRecordingSession({
 *     onStart: () => console.log('Recording started'),
 *     onStop: (blob) => uploadRecording(blob),
 *     onError: (error) => handleError(error),
 *   });
 *
 *   useEffect(() => {
 *     // Initialize when assessment starts
 *     initialize();
 *   }, [initialize]);
 *
 *   return (
 *     <div>
 *       {stream && <CameraPreview stream={stream} isRecording={sessionState === 'recording'} />}
 *       <p>Duration: {duration}s</p>
 *     </div>
 *   );
 * }
 * ```
 */
export function useRecordingSession(
  options: RecordingSessionOptions = {}
): UseRecordingSessionResult {
  const {
    pauseOnHidden = true,
    autoStart = false,
    maxDuration = 0,
    chunkUploadIntervalMs = 10000,
    externalStream = null,
    mixedAudioStream = null,
    onStart,
    onPause,
    onResume,
    onStop,
    onError,
    onMaxDurationReached,
    onChunkReady,
  } = options;

  const [sessionState, setSessionState] = useState<SessionState>('idle');
  const [isPausedByVisibility, setIsPausedByVisibility] = useState(false);
  const wasRecordingBeforeHiddenRef = useRef(false);
  const maxDurationTimeoutRef = useRef<number | null>(null);
  const chunkUploadIntervalRef = useRef<number | null>(null);
  const lastProcessedChunkIndexRef = useRef(0);
  const chunkSequenceRef = useRef(0);

  // Keep refs to current values for use in event handlers (avoids stale closures)
  const sessionStateRef = useLatest(sessionState);
  const onStartRef = useLatest(onStart);
  const onPauseRef = useLatest(onPause);
  const onResumeRef = useLatest(onResume);
  const onStopRef = useLatest(onStop);
  const onErrorRef = useLatest(onError);
  const onMaxDurationReachedRef = useLatest(onMaxDurationReached);
  const onChunkReadyRef = useLatest(onChunkReady);

  const {
    state: recordingState,
    error,
    stream,
    chunks,
    duration,
    start,
    stop,
    pause,
    resume,
    reset: resetRecorder,
    isSupported,
  } = useMediaRecorder({
    video: true,
    audio: true,
    externalStream,
    audioOverrideStream: mixedAudioStream,
  });

  // Keep a ref to chunks to avoid stale closures in interval
  const chunksRef = useLatest(chunks);

  /**
   * Clear max duration timeout.
   */
  const clearMaxDurationTimeout = useCallback(() => {
    if (maxDurationTimeoutRef.current !== null) {
      clearTimeout(maxDurationTimeoutRef.current);
      maxDurationTimeoutRef.current = null;
    }
  }, []);

  /**
   * Set up max duration timeout.
   */
  const setupMaxDurationTimeout = useCallback(() => {
    clearMaxDurationTimeout();
    if (maxDuration > 0) {
      maxDurationTimeoutRef.current = window.setTimeout(() => {
        onMaxDurationReachedRef.current?.();
        // Don't auto-stop, let the caller decide what to do
      }, maxDuration * 1000);
    }
  }, [maxDuration, clearMaxDurationTimeout, onMaxDurationReachedRef]);

  /**
   * Process new chunks and call onChunkReady.
   */
  const processChunks = useCallback(() => {
    const currentChunks = chunksRef.current;
    const lastIndex = lastProcessedChunkIndexRef.current;

    if (currentChunks.length > lastIndex) {
      // Get new chunks since last processing
      const newChunks = currentChunks.slice(lastIndex);
      lastProcessedChunkIndexRef.current = currentChunks.length;

      // Combine new chunks into a single blob
      if (newChunks.length > 0 && onChunkReadyRef.current) {
        const blob = new Blob(newChunks, { type: 'video/webm' });
        const sequence = chunkSequenceRef.current;
        chunkSequenceRef.current += 1;
        onChunkReadyRef.current(blob, sequence);
      }
    }
  }, [chunksRef, onChunkReadyRef]);

  /**
   * Clear chunk upload interval.
   */
  const clearChunkUploadInterval = useCallback(() => {
    if (chunkUploadIntervalRef.current !== null) {
      clearInterval(chunkUploadIntervalRef.current);
      chunkUploadIntervalRef.current = null;
    }
  }, []);

  /**
   * Set up chunk upload interval.
   */
  const setupChunkUploadInterval = useCallback(() => {
    clearChunkUploadInterval();
    if (chunkUploadIntervalMs > 0 && onChunkReadyRef.current) {
      chunkUploadIntervalRef.current = window.setInterval(() => {
        processChunks();
      }, chunkUploadIntervalMs);
    }
  }, [
    chunkUploadIntervalMs,
    clearChunkUploadInterval,
    processChunks,
    onChunkReadyRef,
  ]);

  /**
   * Initialize the session (request permissions and get stream).
   */
  const initialize = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setSessionState('error');
      return false;
    }

    setSessionState('initializing');

    // Reset chunk tracking for new session
    lastProcessedChunkIndexRef.current = 0;
    chunkSequenceRef.current = 0;

    try {
      await start();
      // The start function in useMediaRecorder will handle the permission request
      // and start recording. We need to immediately stop it to just get the stream.
      // Actually, looking at the useMediaRecorder implementation, it starts recording
      // immediately after getting permissions. For a "ready" state, we should
      // modify the approach.

      // For now, we'll start recording as part of initialization
      // The caller can use autoStart=false and call startRecording manually
      if (!autoStart) {
        // We started recording to get the stream, but we should pause if not auto-starting
        pause();
        setSessionState('ready');
      } else {
        setSessionState('recording');
        setupMaxDurationTimeout();
        setupChunkUploadInterval();
        onStartRef.current?.();
      }
      return true;
    } catch {
      setSessionState('error');
      return false;
    }
  }, [
    isSupported,
    start,
    pause,
    autoStart,
    setupMaxDurationTimeout,
    setupChunkUploadInterval,
    onStartRef,
  ]);

  /**
   * Start recording.
   */
  const startRecording = useCallback(async () => {
    if (sessionStateRef.current === 'ready') {
      resume();
      setSessionState('recording');
      setupMaxDurationTimeout();
      setupChunkUploadInterval();
      onStartRef.current?.();
    } else if (sessionStateRef.current === 'idle') {
      // Initialize and start
      setSessionState('initializing');
      // Reset chunk tracking for new session
      lastProcessedChunkIndexRef.current = 0;
      chunkSequenceRef.current = 0;
      await start();
      setSessionState('recording');
      setupMaxDurationTimeout();
      setupChunkUploadInterval();
      onStartRef.current?.();
    }
  }, [
    sessionStateRef,
    resume,
    start,
    setupMaxDurationTimeout,
    setupChunkUploadInterval,
    onStartRef,
  ]);

  /**
   * Stop recording and get final blob.
   */
  const stopRecording = useCallback(async (): Promise<Blob | null> => {
    setSessionState('stopping');
    clearMaxDurationTimeout();
    clearChunkUploadInterval();

    // Process any remaining chunks before stopping
    processChunks();

    const blob = await stop();
    setSessionState('completed');
    onStopRef.current?.(blob);
    return blob;
  }, [
    stop,
    clearMaxDurationTimeout,
    clearChunkUploadInterval,
    processChunks,
    onStopRef,
  ]);

  /**
   * Pause recording.
   */
  const pauseRecording = useCallback(() => {
    if (sessionStateRef.current === 'recording') {
      pause();
      setSessionState('paused');
      clearMaxDurationTimeout();
      clearChunkUploadInterval();
      onPauseRef.current?.();
    }
  }, [
    sessionStateRef,
    pause,
    clearMaxDurationTimeout,
    clearChunkUploadInterval,
    onPauseRef,
  ]);

  /**
   * Resume recording.
   */
  const resumeRecording = useCallback(() => {
    if (sessionStateRef.current === 'paused') {
      resume();
      setSessionState('recording');
      setIsPausedByVisibility(false);
      setupMaxDurationTimeout();
      setupChunkUploadInterval();
      onResumeRef.current?.();
    }
  }, [
    sessionStateRef,
    resume,
    setupMaxDurationTimeout,
    setupChunkUploadInterval,
    onResumeRef,
  ]);

  /**
   * Abandon the session without completing.
   */
  const abandon = useCallback(() => {
    clearMaxDurationTimeout();
    clearChunkUploadInterval();
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
    resetRecorder();
    setSessionState('abandoned');
  }, [
    stream,
    resetRecorder,
    clearMaxDurationTimeout,
    clearChunkUploadInterval,
  ]);

  /**
   * Reset to initial state.
   */
  const reset = useCallback(() => {
    clearMaxDurationTimeout();
    clearChunkUploadInterval();
    resetRecorder();
    setSessionState('idle');
    setIsPausedByVisibility(false);
    lastProcessedChunkIndexRef.current = 0;
    chunkSequenceRef.current = 0;
  }, [resetRecorder, clearMaxDurationTimeout, clearChunkUploadInterval]);

  // Handle visibility changes
  // Note: We use refs for sessionState and callbacks to avoid stale closures
  // and prevent the effect from re-running on every state change.
  const resumeDelayTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (!pauseOnHidden) return;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab became hidden - pause if recording
        if (sessionStateRef.current === 'recording') {
          // Clear any pending resume timeout
          if (resumeDelayTimeoutRef.current !== null) {
            clearTimeout(resumeDelayTimeoutRef.current);
            resumeDelayTimeoutRef.current = null;
          }
          wasRecordingBeforeHiddenRef.current = true;
          pause();
          setSessionState('paused');
          setIsPausedByVisibility(true);
          clearMaxDurationTimeout();
          clearChunkUploadInterval();
          onPauseRef.current?.();
        }
      } else {
        // Tab became visible - resume after brief delay so user sees paused state
        if (
          wasRecordingBeforeHiddenRef.current &&
          sessionStateRef.current === 'paused'
        ) {
          // Brief delay (1.5s) so user can see "Paused" indicator before auto-resume
          resumeDelayTimeoutRef.current = window.setTimeout(() => {
            resumeDelayTimeoutRef.current = null;
            // Double-check we should still resume (user might have manually resumed)
            if (
              wasRecordingBeforeHiddenRef.current &&
              sessionStateRef.current === 'paused'
            ) {
              wasRecordingBeforeHiddenRef.current = false;
              resume();
              setSessionState('recording');
              setIsPausedByVisibility(false);
              setupMaxDurationTimeout();
              setupChunkUploadInterval();
              onResumeRef.current?.();
            }
          }, 1500);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      // Clean up any pending timeout on unmount
      if (resumeDelayTimeoutRef.current !== null) {
        clearTimeout(resumeDelayTimeoutRef.current);
      }
    };
  }, [
    pauseOnHidden,
    pause,
    resume,
    clearMaxDurationTimeout,
    setupMaxDurationTimeout,
    clearChunkUploadInterval,
    setupChunkUploadInterval,
    sessionStateRef,
    onPauseRef,
    onResumeRef,
  ]);

  // Handle recording errors
  useEffect(() => {
    if (error) {
      setSessionState('error');
      clearMaxDurationTimeout();
      onErrorRef.current?.(error);
    }
  }, [error, clearMaxDurationTimeout, onErrorRef]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearMaxDurationTimeout();
      clearChunkUploadInterval();
    };
  }, [clearMaxDurationTimeout, clearChunkUploadInterval]);

  const isActive = sessionState === 'recording' || sessionState === 'paused';

  return {
    sessionState,
    recordingState,
    error,
    stream,
    duration,
    isActive,
    isPausedByVisibility,
    initialize,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    abandon,
    reset,
  };
}

export default useRecordingSession;
