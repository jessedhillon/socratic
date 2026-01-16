import React, { useRef, useEffect } from 'react';
import { useMediaRecorder, type RecordingState } from '../hooks';
import { CameraPreview, type CameraPreviewProps } from '../components';

const recordingStateColors: Record<RecordingState, string> = {
  idle: 'bg-gray-400',
  requesting: 'bg-yellow-400',
  recording: 'bg-red-500',
  paused: 'bg-orange-400',
  stopped: 'bg-green-600',
  error: 'bg-red-600',
};

type PreviewPosition = CameraPreviewProps['position'];

/**
 * Audio-only preview component for when camera is disabled.
 */
const AudioOnlyPreview: React.FC<{ isRecording: boolean }> = ({
  isRecording,
}) => (
  <div className="w-80 h-60 bg-gray-800 rounded-lg flex items-center justify-center text-gray-400">
    <div className="text-center">
      <div className="text-4xl mb-2">🎤</div>
      <div>Audio Only</div>
      {isRecording && (
        <div className="mt-2 flex items-center justify-center gap-2 text-red-400">
          <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          Recording
        </div>
      )}
    </div>
  </div>
);

/**
 * Development test page for A/V capture components.
 *
 * Tests:
 * - useMediaRecorder hook
 * - CameraPreview component (from PR #59)
 * - Blob playback verification
 */
const DevAvTestPage: React.FC = () => {
  const [audioOnly, setAudioOnly] = React.useState(false);
  const [playbackUrl, setPlaybackUrl] = React.useState<string | null>(null);
  const [playbackStatus, setPlaybackStatus] = React.useState<string>('');
  const playbackRef = useRef<HTMLVideoElement>(null);

  // CameraPreview test controls
  const [previewPosition, setPreviewPosition] =
    React.useState<PreviewPosition>('bottom-right');
  const [previewMinimized, setPreviewMinimized] = React.useState(false);
  const [simulateMuted, setSimulateMuted] = React.useState(false);

  const recording = useMediaRecorder({
    video: !audioOnly,
    audio: true,
  });

  // Clean up blob URL when component unmounts or new recording starts
  useEffect(() => {
    return () => {
      if (playbackUrl) {
        URL.revokeObjectURL(playbackUrl);
      }
    };
  }, [playbackUrl]);

  const handlePlayRecording = () => {
    const blob = recording.getBlob();
    if (!blob) {
      setPlaybackStatus('No recording available');
      return;
    }

    // Revoke previous URL if exists
    if (playbackUrl) {
      URL.revokeObjectURL(playbackUrl);
    }

    const url = URL.createObjectURL(blob);
    setPlaybackUrl(url);
    setPlaybackStatus(
      `Blob created: ${(blob.size / 1024).toFixed(1)} KB, type: ${blob.type}`
    );
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleModeChange = () => {
    if (recording.state !== 'idle') {
      recording.reset();
    }
    if (playbackUrl) {
      URL.revokeObjectURL(playbackUrl);
      setPlaybackUrl(null);
      setPlaybackStatus('');
    }
    setAudioOnly(!audioOnly);
  };

  const handleReset = () => {
    recording.reset();
    if (playbackUrl) {
      URL.revokeObjectURL(playbackUrl);
      setPlaybackUrl(null);
      setPlaybackStatus('');
    }
  };

  const hasStream = !!recording.stream;
  const hasVideo = recording.stream?.getVideoTracks().length ?? 0 > 0;

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">A/V Capture Test Page</h1>

        {/* Mode Toggle */}
        <section className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Recording Mode</h2>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={audioOnly}
                onChange={handleModeChange}
                className="w-4 h-4"
              />
              <span>Audio Only (no camera)</span>
            </label>
            <span className="text-sm text-gray-500">
              {audioOnly ? 'Recording audio only' : 'Recording video + audio'}
            </span>
          </div>
        </section>

        {/* Recording State */}
        <section className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Recording Session</h2>
          <div className="flex items-center gap-4 mb-4">
            <span className="font-medium">State:</span>
            <span
              className={`px-3 py-1 rounded-full text-white text-sm font-medium ${recordingStateColors[recording.state]}`}
            >
              {recording.state}
            </span>
            <span className="text-lg font-mono">
              {formatDuration(recording.duration)}
            </span>
            {!recording.isSupported && (
              <span className="text-sm text-red-600">
                (MediaRecorder not supported)
              </span>
            )}
          </div>

          {recording.error && (
            <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-red-700 text-sm">
              <strong>Error:</strong> {recording.error.type} -{' '}
              {recording.error.message}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={recording.start}
              disabled={recording.state !== 'idle'}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Start Recording
            </button>
            <button
              onClick={recording.pause}
              disabled={recording.state !== 'recording'}
              className="px-4 py-2 bg-orange-500 text-white rounded hover:bg-orange-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Pause
            </button>
            <button
              onClick={recording.resume}
              disabled={recording.state !== 'paused'}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Resume
            </button>
            <button
              onClick={() => recording.stop()}
              disabled={
                recording.state !== 'recording' && recording.state !== 'paused'
              }
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Stop
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-800"
            >
              Reset
            </button>
          </div>

          {/* Playback controls - show when stopped */}
          {recording.state === 'stopped' && recording.chunks.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <h3 className="font-medium mb-2">Playback Test</h3>
              <button
                onClick={handlePlayRecording}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                Play Recording
              </button>
              {playbackStatus && (
                <span className="ml-3 text-sm text-gray-600">
                  {playbackStatus}
                </span>
              )}
              {playbackUrl && (
                <div className="mt-3">
                  <video
                    ref={playbackRef}
                    src={playbackUrl}
                    controls
                    autoPlay
                    className="w-80 h-60 bg-black rounded-lg"
                    onPlay={() => setPlaybackStatus((s) => s + ' | Playing...')}
                    onEnded={() =>
                      setPlaybackStatus((s) => s + ' | Playback complete!')
                    }
                    onError={(e) =>
                      setPlaybackStatus(
                        `Error: ${(e.target as HTMLVideoElement).error?.message || 'Unknown'}`
                      )
                    }
                  />
                </div>
              )}
            </div>
          )}
        </section>

        {/* CameraPreview Component Test */}
        <section className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            CameraPreview Component Test
          </h2>

          {/* Preview Controls */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-2">Position</label>
              <select
                value={previewPosition}
                onChange={(e) =>
                  setPreviewPosition(e.target.value as PreviewPosition)
                }
                className="w-full border rounded px-3 py-2"
              >
                <option value="top-left">Top Left</option>
                <option value="top-right">Top Right</option>
                <option value="bottom-left">Bottom Left</option>
                <option value="bottom-right">Bottom Right</option>
              </select>
            </div>
            <div className="flex flex-col justify-end gap-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={previewMinimized}
                  onChange={(e) => setPreviewMinimized(e.target.checked)}
                  className="w-4 h-4"
                />
                <span>Start Minimized</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={simulateMuted}
                  onChange={(e) => setSimulateMuted(e.target.checked)}
                  className="w-4 h-4"
                />
                <span>Simulate Muted</span>
              </label>
            </div>
          </div>

          {/* Preview Status */}
          <div className="bg-gray-50 rounded p-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <strong>Has Stream:</strong> {hasStream ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Has Video:</strong> {hasVideo ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Is Recording:</strong>{' '}
                {recording.state === 'recording' ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Muted:</strong> {simulateMuted ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Position:</strong> {previewPosition}
              </div>
              <div>
                <strong>Minimized:</strong> {previewMinimized ? 'Yes' : 'No'}
              </div>
            </div>
          </div>

          <p className="text-sm text-gray-500 mt-4">
            The CameraPreview component renders as a fixed overlay in the corner
            of the screen.
            {!hasStream && ' Start recording to see the preview.'}
          </p>
        </section>

        {/* Audio-only fallback preview */}
        {audioOnly && hasStream && (
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Audio Preview</h2>
            <div className="flex justify-center">
              <AudioOnlyPreview isRecording={recording.state === 'recording'} />
            </div>
          </section>
        )}

        {/* Recording Stats */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Recording Details</h2>
          <pre className="bg-gray-50 rounded p-4 text-sm overflow-auto">
            {JSON.stringify(
              {
                state: recording.state,
                duration: recording.duration,
                hasStream: !!recording.stream,
                hasError: !!recording.error,
                chunksCount: recording.chunks.length,
                totalSize: recording.chunks.reduce((sum, c) => sum + c.size, 0),
                isSupported: recording.isSupported,
                audioOnly,
                previewPosition,
                previewMinimized,
                simulateMuted,
              },
              null,
              2
            )}
          </pre>
        </section>
      </div>

      {/* CameraPreview component - renders as fixed overlay */}
      {!audioOnly && (
        <CameraPreview
          stream={recording.stream}
          isRecording={recording.state === 'recording'}
          hasAudio={true}
          isMuted={simulateMuted}
          defaultMinimized={previewMinimized}
          position={previewPosition}
          onMinimizeChange={setPreviewMinimized}
        />
      )}
    </div>
  );
};

export default DevAvTestPage;
