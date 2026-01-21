import React, { useEffect, useState, useRef, useMemo } from 'react';
import type { UtteranceType } from '../../api';

export interface ChatMessageData {
  id: string;
  type: UtteranceType;
  content: string;
  timestamp?: string;
  isStreaming?: boolean;
}

interface ChatMessageProps {
  message: ChatMessageData;
  /** Whether this message is currently being spoken */
  isSpeaking?: boolean;
  /** Callback to skip the speech */
  onSkipSpeech?: () => void;
  /** Whether to animate the text reveal (typewriter effect) */
  animateReveal?: boolean;
  /** Callback when animation completes */
  onAnimationComplete?: () => void;
  /** Actual audio duration in seconds (preferred over estimation) */
  audioDurationSeconds?: number | null;
  /** Speech speed for estimating animation duration when audioDurationSeconds is not available (default 1.1) */
  speechSpeed?: number;
}

/** Base characters per minute for TTS at 1.0x speed (approx 180 wpm * 5 chars/word) */
const BASE_CHARS_PER_MINUTE = 900;
/** Minimum interval between ticks in ms */
const MIN_TICK_INTERVAL_MS = 16;
/** Characters to reveal per tick */
const CHARS_PER_TICK = 2;

/**
 * A single message bubble in the assessment chat interface.
 */
const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  isSpeaking = false,
  onSkipSpeech,
  animateReveal = false,
  onAnimationComplete,
  audioDurationSeconds,
  speechSpeed = 1.1,
}) => {
  const isLearner = message.type === 'learner';
  const isSystem = message.type === 'system';
  const isInterviewer = message.type === 'interviewer';

  // Typewriter animation state
  const [revealedLength, setRevealedLength] = useState(
    animateReveal ? 0 : message.content.length
  );
  const animationCompleteRef = useRef(false);

  // Calculate tick interval to match audio duration (actual or estimated)
  const tickIntervalMs = useMemo(() => {
    if (!animateReveal || message.content.length === 0)
      return MIN_TICK_INTERVAL_MS;

    let durationMs: number;

    // Use actual audio duration if available, otherwise estimate
    if (audioDurationSeconds && audioDurationSeconds > 0) {
      durationMs = audioDurationSeconds * 1000;
    } else {
      // Estimate audio duration: chars / (charsPerMinute * speedMultiplier) * 60000ms
      const charsPerMinute = BASE_CHARS_PER_MINUTE * speechSpeed;
      durationMs = (message.content.length / charsPerMinute) * 60000;
    }

    // Calculate interval: totalDuration / (totalChars / charsPerTick)
    const totalTicks = Math.ceil(message.content.length / CHARS_PER_TICK);
    const interval = Math.max(MIN_TICK_INTERVAL_MS, durationMs / totalTicks);

    return interval;
  }, [
    animateReveal,
    message.content.length,
    audioDurationSeconds,
    speechSpeed,
  ]);

  // Run typewriter animation
  useEffect(() => {
    if (!animateReveal || revealedLength >= message.content.length) {
      // Animation complete
      if (animateReveal && !animationCompleteRef.current) {
        animationCompleteRef.current = true;
        onAnimationComplete?.();
      }
      return;
    }

    const timer = setInterval(() => {
      setRevealedLength((prev) => {
        const next = Math.min(prev + CHARS_PER_TICK, message.content.length);
        return next;
      });
    }, tickIntervalMs);

    return () => clearInterval(timer);
  }, [
    animateReveal,
    revealedLength,
    message.content.length,
    onAnimationComplete,
    tickIntervalMs,
  ]);

  // Reset animation when message changes
  useEffect(() => {
    if (animateReveal) {
      setRevealedLength(0);
      animationCompleteRef.current = false;
    } else {
      setRevealedLength(message.content.length);
    }
  }, [message.id, animateReveal, message.content.length]);

  const isAnimating = animateReveal && revealedLength < message.content.length;
  const displayContent = animateReveal
    ? message.content.slice(0, revealedLength)
    : message.content;

  if (isSystem) {
    return (
      <div className="flex justify-center my-4">
        <div className="bg-gray-100 text-gray-600 text-sm px-4 py-2 rounded-lg max-w-md text-center">
          {message.content}
        </div>
      </div>
    );
  }

  // Learner messages: simple right-aligned bubble
  if (isLearner) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%] px-4 py-3 rounded-2xl bg-blue-600 text-white rounded-br-md">
          <div className="whitespace-pre-wrap">
            {displayContent}
            {(message.isStreaming || isAnimating) && (
              <span className="ml-1 animate-pulse">▊</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Interviewer messages: bubble with skip button outside, at fixed position
  return (
    <div className="flex justify-start mb-4">
      {/* Container at max bubble width so skip button position is stable */}
      <div className="w-[80%]">
        {/* Bubble only takes space needed for content */}
        <div className="inline-block max-w-full px-4 py-3 rounded-2xl bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-md">
          <div className="text-xs text-gray-500 mb-1 font-medium">
            Interviewer
          </div>
          <div className="whitespace-pre-wrap">
            {displayContent}
            {(message.isStreaming || isAnimating) && (
              <span className="ml-1 animate-pulse">▊</span>
            )}
          </div>
        </div>
        {/* Skip button outside bubble, right-aligned to the max-width container */}
        {isSpeaking && onSkipSpeech && (
          <div className="flex justify-end mt-1">
            <button
              onClick={onSkipSpeech}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
              title="Skip to end"
            >
              <span>Skip</span>
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
