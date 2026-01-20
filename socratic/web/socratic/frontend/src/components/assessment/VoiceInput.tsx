/**
 * Voice input component for speech-to-text recording.
 *
 * Phases:
 * 1. Idle - "Click to record" button
 * 2. Recording - Timer, stop button
 * 3. Transcribing - Loading spinner
 * 4. Review - Editable text field, "Send" and "Re-record" buttons
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useMediaRecorder, useTranscription } from '../../hooks';

export interface VoiceInputProps {
  /** Called when the user confirms the transcribed text */
  onSubmit: (text: string) => void;
  /** Whether input is disabled */
  disabled?: boolean;
  /** Placeholder text for the review textarea */
  placeholder?: string;
}

type Phase = 'idle' | 'recording' | 'transcribing' | 'review';

/**
 * Voice input component that records audio, transcribes it, and allows editing before sending.
 */
const VoiceInput: React.FC<VoiceInputProps> = ({
  onSubmit,
  disabled = false,
  placeholder = 'Edit your response if needed...',
}) => {
  const [phase, setPhase] = useState<Phase>('idle');
  const [editedText, setEditedText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    state: recordingState,
    duration,
    start: startRecording,
    stop: stopRecording,
    reset: resetRecording,
    getBlob,
    isSupported,
  } = useMediaRecorder({
    audio: true,
    video: false,
  });

  const {
    state: transcriptionState,
    result: transcriptionResult,
    error: transcriptionError,
    transcribe,
    reset: resetTranscription,
  } = useTranscription();

  // Format duration as MM:SS
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle recording state changes
  useEffect(() => {
    if (recordingState === 'recording') {
      setPhase('recording');
    }
  }, [recordingState]);

  // Handle transcription completion
  useEffect(() => {
    if (transcriptionState === 'success' && transcriptionResult) {
      setEditedText(transcriptionResult.text);
      setPhase('review');
      // Focus textarea after transition
      setTimeout(() => textareaRef.current?.focus(), 100);
    } else if (transcriptionState === 'error') {
      setPhase('idle');
    }
  }, [transcriptionState, transcriptionResult]);

  const handleStartRecording = useCallback(async () => {
    if (disabled) return;
    resetTranscription();
    await startRecording();
  }, [disabled, startRecording, resetTranscription]);

  const handleStopRecording = useCallback(async () => {
    setPhase('transcribing');
    await stopRecording();

    // Get the recorded audio blob
    const blob = getBlob();
    if (blob) {
      await transcribe(blob);
    } else {
      setPhase('idle');
    }
  }, [stopRecording, getBlob, transcribe]);

  const handleReRecord = useCallback(() => {
    resetRecording();
    resetTranscription();
    setEditedText('');
    setPhase('idle');
  }, [resetRecording, resetTranscription]);

  const handleSubmit = useCallback(() => {
    const trimmed = editedText.trim();
    if (trimmed) {
      onSubmit(trimmed);
      handleReRecord();
    }
  }, [editedText, onSubmit, handleReRecord]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (!isSupported) {
    return (
      <div className="text-center text-gray-500 py-4">
        Voice input is not supported in this browser.
      </div>
    );
  }

  // Render based on current phase
  switch (phase) {
    case 'idle':
      return (
        <div className="flex items-center gap-3">
          <button
            onClick={handleStartRecording}
            disabled={disabled}
            className="flex items-center gap-2 px-4 py-3 bg-red-600 text-white rounded-xl font-medium hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            title="Click to start recording"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
            Record
          </button>
          {transcriptionError && (
            <span className="text-red-500 text-sm">
              {transcriptionError.message}
            </span>
          )}
        </div>
      );

    case 'recording':
      return (
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-3 bg-red-100 text-red-700 rounded-xl">
            <span className="w-3 h-3 bg-red-600 rounded-full animate-pulse" />
            <span className="font-mono">{formatDuration(duration)}</span>
          </div>
          <button
            onClick={handleStopRecording}
            className="flex items-center gap-2 px-4 py-3 bg-gray-800 text-white rounded-xl font-medium hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
            Stop
          </button>
        </div>
      );

    case 'transcribing':
      return (
        <div className="flex items-center gap-3 px-4 py-3 bg-blue-50 text-blue-700 rounded-xl">
          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>Transcribing...</span>
        </div>
      );

    case 'review':
      return (
        <div className="flex flex-col gap-3">
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={3}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              style={{ minHeight: '80px', maxHeight: '200px' }}
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleReRecord}
              className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
            >
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
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Re-record
            </button>
            <button
              onClick={handleSubmit}
              disabled={!editedText.trim()}
              className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      );
  }
};

export default VoiceInput;
