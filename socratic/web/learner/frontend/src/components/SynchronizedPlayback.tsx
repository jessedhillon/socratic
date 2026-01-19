import React, { useRef, useState, useEffect, useCallback } from 'react';

export interface WordTiming {
  word: string;
  start: number; // seconds
  end: number; // seconds
}

export interface SynchronizedPlaybackProps {
  /** URL of the media (audio or video) to play */
  mediaUrl: string;
  /** Whether the media is video (true) or audio-only (false) */
  isVideo?: boolean;
  /** Word-level timing data from transcription */
  wordTimings: WordTiming[];
  /** Optional class name for the container */
  className?: string;
}

/**
 * SynchronizedPlayback component displays a media player with synchronized
 * transcript that highlights words as they are spoken.
 *
 * Features:
 * - Real-time word highlighting during playback
 * - Click any word to seek to that timestamp
 * - Works with both audio and video
 */
const SynchronizedPlayback: React.FC<SynchronizedPlaybackProps> = ({
  mediaUrl,
  isVideo = false,
  wordTimings,
  className = '',
}) => {
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);

  // Find the current word index based on playback time
  const currentWordIndex = wordTimings.findIndex(
    (w) => currentTime >= w.start && currentTime < w.end
  );

  // Update current time during playback
  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;

    const handleTimeUpdate = () => {
      setCurrentTime(media.currentTime);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    const handleLoadedMetadata = () => setDuration(media.duration);

    media.addEventListener('timeupdate', handleTimeUpdate);
    media.addEventListener('play', handlePlay);
    media.addEventListener('pause', handlePause);
    media.addEventListener('ended', handleEnded);
    media.addEventListener('loadedmetadata', handleLoadedMetadata);

    return () => {
      media.removeEventListener('timeupdate', handleTimeUpdate);
      media.removeEventListener('play', handlePlay);
      media.removeEventListener('pause', handlePause);
      media.removeEventListener('ended', handleEnded);
      media.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, []);

  // Handle clicking on a word to seek
  const handleWordClick = useCallback(
    (wordIndex: number) => {
      const media = mediaRef.current;
      if (!media || wordIndex < 0 || wordIndex >= wordTimings.length) return;

      const word = wordTimings[wordIndex];
      media.currentTime = word.start;
      setCurrentTime(word.start);
    },
    [wordTimings]
  );

  // Format time as mm:ss
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`synchronized-playback ${className}`}>
      {/* Media Player */}
      <div className="mb-4">
        {isVideo ? (
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            src={mediaUrl}
            controls
            className="w-full max-w-lg rounded-lg bg-black"
          />
        ) : (
          <audio
            ref={mediaRef as React.RefObject<HTMLAudioElement>}
            src={mediaUrl}
            controls
            className="w-full max-w-lg"
          />
        )}
      </div>

      {/* Playback Info */}
      <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
        <span>
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
        <span
          className={`px-2 py-0.5 rounded ${isPlaying ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
        >
          {isPlaying ? 'Playing' : 'Paused'}
        </span>
        {currentWordIndex >= 0 && (
          <span className="text-blue-600">
            Word {currentWordIndex + 1} of {wordTimings.length}
          </span>
        )}
      </div>

      {/* Synchronized Transcript */}
      <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-auto">
        <p className="leading-relaxed">
          {wordTimings.map((word, index) => {
            const isCurrent = index === currentWordIndex;
            const isPast = currentTime >= word.end;

            return (
              <span
                key={index}
                onClick={() => handleWordClick(index)}
                className={`
                  cursor-pointer px-0.5 rounded transition-colors duration-100
                  ${isCurrent ? 'bg-yellow-300 text-black font-medium' : ''}
                  ${isPast && !isCurrent ? 'text-gray-500' : ''}
                  ${!isPast && !isCurrent ? 'text-gray-800' : ''}
                  hover:bg-blue-100
                `}
                title={`${formatTime(word.start)} - ${formatTime(word.end)}`}
              >
                {word.word}
              </span>
            );
          })}
        </p>
      </div>

      {/* Instructions */}
      <p className="text-xs text-gray-500 mt-2">
        Click any word to jump to that position in the audio.
      </p>
    </div>
  );
};

export default SynchronizedPlayback;
