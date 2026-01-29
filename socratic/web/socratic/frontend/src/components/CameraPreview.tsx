import React, { useEffect, useRef, useState } from 'react';

export interface CameraPreviewProps {
  /** The media stream to display */
  stream: MediaStream | null;
  /** Whether recording is active */
  isRecording?: boolean;
  /** Whether audio is being captured */
  hasAudio?: boolean;
  /** Whether audio is muted */
  isMuted?: boolean;
  /** Initial minimized state */
  defaultMinimized?: boolean;
  /** Position of the preview */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  /** Callback when minimize state changes */
  onMinimizeChange?: (minimized: boolean) => void;
  /** Show placeholder when no stream (for mock/preview mode) */
  showPlaceholder?: boolean;
  /** Show audio level indicator */
  showAudioLevel?: boolean;
}

/**
 * Camera preview component showing the learner's camera feed.
 *
 * Features:
 * - Mirrored video (learners expect mirrored self-view)
 * - Recording indicator (pulsing red dot)
 * - Minimize/expand functionality
 * - Mute indicator when audio is captured but muted
 * - Non-intrusive corner positioning
 */
export function CameraPreview({
  stream,
  isRecording = false,
  hasAudio = false,
  isMuted = false,
  defaultMinimized = false,
  position = 'bottom-right',
  onMinimizeChange,
  showPlaceholder = false,
  showAudioLevel = false,
}: CameraPreviewProps): React.ReactElement | null {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [minimized, setMinimized] = useState(defaultMinimized);
  const [audioLevel, setAudioLevel] = useState(0);

  // Web Audio API refs for audio level analysis
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Attach stream to video element
  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  // Set up audio level analysis
  useEffect(() => {
    if (!showAudioLevel || !stream) {
      setAudioLevel(0);
      return;
    }

    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
      return;
    }

    // Create audio context and analyser
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    analyserRef.current = analyser;

    // Create source from stream audio track
    const audioOnlyStream = new MediaStream(audioTracks);
    const source = audioContext.createMediaStreamSource(audioOnlyStream);
    sourceRef.current = source;
    source.connect(analyser);

    // Buffer for frequency data
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    // Animation loop to update audio level
    const updateLevel = () => {
      if (!analyserRef.current) return;

      analyserRef.current.getByteFrequencyData(dataArray);

      // Calculate average level from frequency data
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;

      // Normalize to 0-1 range (values are 0-255)
      const normalizedLevel = Math.min(average / 128, 1);
      setAudioLevel(normalizedLevel);

      animationFrameRef.current = requestAnimationFrame(updateLevel);
    };

    // Start the animation loop
    animationFrameRef.current = requestAnimationFrame(updateLevel);

    // Cleanup
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (sourceRef.current) {
        sourceRef.current.disconnect();
        sourceRef.current = null;
      }
      if (analyserRef.current) {
        analyserRef.current.disconnect();
        analyserRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      setAudioLevel(0);
    };
  }, [showAudioLevel, stream]);

  const handleMinimize = () => {
    const newState = !minimized;
    setMinimized(newState);
    onMinimizeChange?.(newState);
  };

  if (!stream && !showPlaceholder) {
    return null;
  }

  // Position classes
  const positionClasses = {
    'top-left': 'top-4 left-4',
    'top-right': 'top-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'bottom-right': 'bottom-4 right-4',
  };

  return (
    <div
      className={`fixed ${positionClasses[position]} z-50 transition-all duration-300 ${
        minimized ? 'w-12 h-12' : 'w-48 h-36'
      }`}
    >
      {/* Video container */}
      <div
        className={`relative bg-black rounded-lg overflow-hidden shadow-lg ${
          minimized ? 'w-12 h-12' : 'w-full h-full'
        }`}
      >
        {/* Video element - mirrored horizontally */}
        {stream ? (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`w-full h-full object-cover ${minimized ? 'hidden' : 'block'}`}
            style={{ transform: 'scaleX(-1)' }}
          />
        ) : (
          /* Placeholder when no stream */
          !minimized && (
            <div className="w-full h-full flex items-center justify-center bg-gray-700">
              <svg
                className="w-12 h-12 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
            </div>
          )
        )}

        {/* Minimized state - show camera icon */}
        {minimized && (
          <div className="w-full h-full flex items-center justify-center bg-gray-800">
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
          </div>
        )}

        {/* Recording indicator */}
        {isRecording && (
          <div className="absolute top-2 left-2 flex items-center gap-1">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            {!minimized && (
              <span className="text-xs text-white font-medium drop-shadow">
                REC
              </span>
            )}
          </div>
        )}

        {/* Mute indicator */}
        {hasAudio && isMuted && !minimized && (
          <div className="absolute top-2 right-8 text-white drop-shadow">
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
                d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
              />
            </svg>
          </div>
        )}

        {/* Audio level indicator */}
        {showAudioLevel && !minimized && stream && (
          <div className="absolute bottom-2 left-2 right-2 h-1.5 bg-black/30 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-75"
              style={{ width: `${audioLevel * 100}%` }}
            />
          </div>
        )}

        {/* Minimize/expand button */}
        <button
          onClick={handleMinimize}
          className={`absolute ${minimized ? 'inset-0' : 'top-2 right-2'} ${
            minimized ? '' : 'p-1 rounded bg-black/50 hover:bg-black/70'
          } text-white transition-colors`}
          aria-label={minimized ? 'Expand preview' : 'Minimize preview'}
        >
          {minimized ? (
            // Invisible click target for minimized state
            <span className="sr-only">Expand preview</span>
          ) : (
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
                d="M19 9l-7 7-7-7"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

export default CameraPreview;
