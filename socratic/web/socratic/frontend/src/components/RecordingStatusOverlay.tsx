import React, { useEffect, useRef, useState } from 'react';

export interface RecordingStatusOverlayProps {
  /** Whether recording is active */
  isRecording: boolean;
  /** Whether recording is paused */
  isPaused?: boolean;
  /** Elapsed recording time in seconds */
  durationSeconds: number;
  /** Whether paused due to tab visibility */
  isPausedByVisibility?: boolean;
  /** The media stream for audio level monitoring (optional) */
  stream?: MediaStream | null;
  /** Whether to show the audio level meter */
  showAudioLevel?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format seconds to mm:ss display.
 */
const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

/**
 * Hook for monitoring audio level from a media stream.
 */
function useAudioLevel(
  stream: MediaStream | null | undefined,
  enabled: boolean
): number {
  const [level, setLevel] = useState(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!stream || !enabled) {
      setLevel(0);
      return;
    }

    // Check if stream has audio tracks
    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
      return;
    }

    try {
      // Create audio context and analyser
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      // Connect stream to analyser
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      // Create data array for frequency data
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      // Update level on each animation frame
      const updateLevel = () => {
        analyser.getByteFrequencyData(dataArray);

        // Calculate average level
        const sum = dataArray.reduce((acc, val) => acc + val, 0);
        const average = sum / dataArray.length;
        const normalizedLevel = Math.min(average / 128, 1); // Normalize to 0-1

        setLevel(normalizedLevel);
        animationFrameRef.current = requestAnimationFrame(updateLevel);
      };

      updateLevel();
    } catch (err) {
      console.error('Failed to create audio level monitor:', err);
    }

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, [stream, enabled]);

  return level;
}

/**
 * Recording status overlay component for the assessment view.
 *
 * Displays:
 * - Recording indicator (pulsing red dot)
 * - Recording status text (Recording/Paused)
 * - Elapsed time display (mm:ss)
 * - Optional audio level meter
 *
 * @example
 * ```tsx
 * <RecordingStatusOverlay
 *   isRecording={sessionState === 'recording'}
 *   isPaused={sessionState === 'paused'}
 *   durationSeconds={duration}
 *   stream={stream}
 *   showAudioLevel
 * />
 * ```
 */
export function RecordingStatusOverlay({
  isRecording,
  isPaused = false,
  durationSeconds,
  isPausedByVisibility = false,
  stream,
  showAudioLevel = false,
  className = '',
}: RecordingStatusOverlayProps): React.ReactElement {
  const audioLevel = useAudioLevel(stream, showAudioLevel && isRecording);

  const isActive = isRecording || isPaused;

  return (
    <div
      className={`flex items-center gap-4 px-4 py-2 bg-gray-900/90 rounded-lg shadow-lg ${className}`}
    >
      {/* Recording indicator */}
      <div className="flex items-center gap-2">
        {isActive && (
          <span className="relative flex h-3 w-3">
            {isRecording && !isPaused && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            )}
            <span
              className={`relative inline-flex rounded-full h-3 w-3 ${
                isPaused ? 'bg-yellow-500' : 'bg-red-500'
              }`}
            ></span>
          </span>
        )}
        <span
          className={`text-sm font-medium ${
            isPaused ? 'text-yellow-400' : 'text-red-400'
          }`}
        >
          {isPaused ? 'Paused' : isRecording ? 'Recording' : 'Ready'}
        </span>
      </div>

      {/* Visibility pause indicator */}
      {isPausedByVisibility && (
        <div className="flex items-center gap-1 text-yellow-400 text-xs">
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
            />
          </svg>
          <span>Tab hidden</span>
        </div>
      )}

      {/* Duration */}
      <div className="flex items-center gap-2 text-white">
        <svg
          className="w-4 h-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span className="font-mono text-sm tabular-nums">
          {formatDuration(durationSeconds)}
        </span>
      </div>

      {/* Audio level meter */}
      {showAudioLevel && isRecording && !isPaused && (
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
            />
          </svg>
          <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-75 ${
                audioLevel > 0.8
                  ? 'bg-red-500'
                  : audioLevel > 0.5
                    ? 'bg-yellow-500'
                    : 'bg-green-500'
              }`}
              style={{ width: `${Math.max(audioLevel * 100, 5)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default RecordingStatusOverlay;
