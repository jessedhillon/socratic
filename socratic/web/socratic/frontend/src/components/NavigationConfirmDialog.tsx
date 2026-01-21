import React from 'react';

export interface NavigationConfirmDialogProps {
  /** Whether the dialog is visible */
  isOpen: boolean;
  /** Title of the dialog */
  title?: string;
  /** Warning message to display */
  message?: string;
  /** Text for the confirm (leave) button */
  confirmText?: string;
  /** Text for the cancel (stay) button */
  cancelText?: string;
  /** Called when user confirms leaving */
  onConfirm: () => void;
  /** Called when user cancels and wants to stay */
  onCancel: () => void;
}

/**
 * Confirmation dialog shown when user tries to navigate away during an active session.
 *
 * Features:
 * - Modal overlay with backdrop blur
 * - Clear warning message
 * - Prominent cancel button (encouraged action)
 * - Less prominent confirm button (discouraged action)
 */
export const NavigationConfirmDialog: React.FC<
  NavigationConfirmDialogProps
> = ({
  isOpen,
  title = 'Leave Assessment?',
  message = 'Your recording will be stopped and your assessment progress may be lost. This attempt may be consumed.',
  confirmText = 'Leave',
  cancelText = 'Stay',
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="navigation-confirm-title"
    >
      <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        {/* Warning icon */}
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
          <svg
            className="h-6 w-6 text-amber-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Title */}
        <h2
          id="navigation-confirm-title"
          className="mb-2 text-center text-xl font-semibold text-gray-900"
        >
          {title}
        </h2>

        {/* Message */}
        <p className="mb-6 text-center text-gray-600">{message}</p>

        {/* Warning list */}
        <div className="mb-6 rounded-lg bg-amber-50 p-4">
          <ul className="space-y-2 text-sm text-amber-800">
            <li className="flex items-start gap-2">
              <svg
                className="mt-0.5 h-4 w-4 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>Your recording will be stopped immediately</span>
            </li>
            <li className="flex items-start gap-2">
              <svg
                className="mt-0.5 h-4 w-4 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>Assessment progress will be lost</span>
            </li>
            <li className="flex items-start gap-2">
              <svg
                className="mt-0.5 h-4 w-4 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>This attempt may count toward your limit</span>
            </li>
          </ul>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-3 font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-3 font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default NavigationConfirmDialog;
