/**
 * Button component for playing text as speech.
 *
 * Provides a speaker icon button that converts text to speech
 * and plays it when clicked. Shows loading and playing states.
 */

import { useSpeech, type Voice } from '../../hooks';

interface SpeakButtonProps {
  /** Text to speak when clicked */
  text: string;
  /** Voice to use for synthesis */
  voice?: Voice;
  /** Speech speed (0.25-4.0) */
  speed?: number;
  /** Additional CSS classes */
  className?: string;
  /** Accessible label */
  ariaLabel?: string;
  /** Whether the button is disabled */
  disabled?: boolean;
}

/**
 * Button that speaks text using TTS when clicked.
 *
 * Shows different states:
 * - Default: Speaker icon
 * - Loading: Spinner icon (while synthesizing)
 * - Playing: Sound wave animation
 *
 * Clicking while playing will stop the audio.
 */
export function SpeakButton({
  text,
  voice = 'nova',
  speed = 1.0,
  className = '',
  ariaLabel = 'Speak text',
  disabled = false,
}: SpeakButtonProps) {
  const { state, speak, stop } = useSpeech();

  const handleClick = async () => {
    if (state.isPlaying) {
      stop();
      return;
    }

    if (state.isLoading) {
      return;
    }

    try {
      await speak(text, { voice, speed, autoPlay: true });
    } catch {
      // Error is already captured in state
    }
  };

  const isActive = state.isLoading || state.isPlaying;

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || !text}
      aria-label={state.isPlaying ? 'Stop speaking' : ariaLabel}
      className={`inline-flex items-center justify-center p-2 rounded-full transition-colors ${
        isActive
          ? 'bg-blue-100 text-blue-600'
          : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      {state.isLoading ? (
        <LoadingIcon />
      ) : state.isPlaying ? (
        <PlayingIcon />
      ) : (
        <SpeakerIcon />
      )}
    </button>
  );
}

function SpeakerIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

function LoadingIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="animate-spin"
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

function PlayingIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  );
}

/**
 * Hook-based alternative for more control over speech playback.
 * Use this when you need custom UI or more control over the speech state.
 */
export { useSpeech } from '../../hooks';
