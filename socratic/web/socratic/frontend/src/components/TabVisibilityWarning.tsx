import React from 'react';

export interface TabVisibilityWarningProps {
  /** Whether the warning should be visible */
  isVisible: boolean;
  /** Optional custom message */
  message?: string;
}

/**
 * Full-screen modal overlay that warns the learner when they've navigated away
 * from the assessment tab and recording is paused.
 */
export const TabVisibilityWarning: React.FC<TabVisibilityWarningProps> = ({
  isVisible,
  message = 'Recording is paused because you left this tab.',
}) => {
  if (!isVisible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      <div className="max-w-md mx-4 p-8 bg-white rounded-2xl shadow-2xl text-center">
        {/* Warning icon */}
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-amber-100 flex items-center justify-center">
          <svg
            className="w-8 h-8 text-amber-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Title */}
        <h2 className="text-xl font-semibold text-gray-900 mb-3">
          Assessment Paused
        </h2>

        {/* Message */}
        <p className="text-gray-600 mb-6">{message}</p>

        {/* Instructions */}
        <div className="p-4 bg-blue-50 rounded-lg mb-6">
          <p className="text-sm text-blue-800">
            Recording will automatically resume when you return to this tab.
          </p>
        </div>

        {/* Pulsing indicator */}
        <div className="flex items-center justify-center gap-2 text-amber-600">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
          </span>
          <span className="text-sm font-medium">
            Waiting for you to return...
          </span>
        </div>
      </div>
    </div>
  );
};

export default TabVisibilityWarning;
