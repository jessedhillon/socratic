import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useMediaPermissions } from '../hooks/useMediaPermissions';

export interface PermissionGateProps {
  /** Content to render when permissions are granted */
  children: React.ReactNode;
  /** Whether to request camera access (default: true) */
  camera?: boolean;
  /** Whether to request microphone access (default: true) */
  microphone?: boolean;
  /** Callback when permissions are granted */
  onGranted?: () => void;
  /** Callback when permissions are denied */
  onDenied?: () => void;
  /** Custom title for the permission prompt */
  title?: string;
  /** Custom description for why permissions are needed */
  description?: string;
}

/**
 * Component that gates content behind camera/microphone permissions.
 *
 * Displays appropriate UI for:
 * - Checking permission state
 * - Requesting permissions
 * - Permission denied with instructions
 * - Unsupported browsers
 *
 * Note: This component only verifies permissions - it does not acquire or hold
 * a media stream. The camera/microphone will only be active when you actually
 * start recording via useMediaRecorder.
 *
 * @example
 * ```tsx
 * <PermissionGate
 *   onGranted={() => console.log('Ready to record')}
 *   title="Camera Access Required"
 *   description="We need access to your camera and microphone to conduct the assessment."
 * >
 *   <AssessmentInterface />
 * </PermissionGate>
 * ```
 */
export function PermissionGate({
  children,
  camera = true,
  microphone = true,
  onGranted,
  onDenied,
  title = 'Camera & Microphone Access',
  description = 'This assessment requires access to your camera and microphone.',
}: PermissionGateProps): React.ReactElement {
  const {
    allGranted,
    anyDenied,
    isSupported,
    isChecking,
    requestPermissions,
    getStatusMessage,
    getDeniedInstructions,
  } = useMediaPermissions();

  const [isRequesting, setIsRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  // Track if we've already called onGranted to prevent double-firing
  const grantedCalledRef = useRef(false);

  // Call onGranted when permissions are already granted on mount
  useEffect(() => {
    if (allGranted && !isChecking && !grantedCalledRef.current) {
      grantedCalledRef.current = true;
      onGranted?.();
    }
  }, [allGranted, isChecking, onGranted]);

  const handleRequestPermissions = useCallback(async () => {
    setIsRequesting(true);
    setRequestError(null);

    const result = await requestPermissions({ camera, microphone });

    setIsRequesting(false);

    if (result.success) {
      grantedCalledRef.current = true;
      onGranted?.();
    } else {
      setRequestError(result.error);
      if (result.errorType === 'denied') {
        onDenied?.();
      }
    }
  }, [camera, microphone, requestPermissions, onGranted, onDenied]);

  // Show loading while checking permissions
  if (isChecking) {
    return (
      <div className="flex flex-col items-center justify-center min-h-64 p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
        <p className="text-gray-600">Checking permissions...</p>
      </div>
    );
  }

  // Permissions granted - render children
  if (allGranted) {
    return <>{children}</>;
  }

  // Unsupported browser
  if (!isSupported) {
    return (
      <div className="flex flex-col items-center justify-center min-h-64 p-8 text-center">
        <div className="bg-red-100 rounded-full p-4 mb-4">
          <svg
            className="w-8 h-8 text-red-600"
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
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Browser Not Supported
        </h2>
        <p className="text-gray-600 max-w-md">{getStatusMessage()}</p>
      </div>
    );
  }

  // Permission denied
  if (anyDenied) {
    const instructions = getDeniedInstructions();
    return (
      <div className="flex flex-col items-center justify-center min-h-64 p-8 text-center">
        <div className="bg-yellow-100 rounded-full p-4 mb-4">
          <svg
            className="w-8 h-8 text-yellow-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Permission Blocked
        </h2>
        <p className="text-gray-600 mb-4 max-w-md">{getStatusMessage()}</p>
        {instructions && (
          <div className="bg-gray-100 rounded-lg p-4 max-w-md">
            <p className="text-sm text-gray-700">{instructions}</p>
          </div>
        )}
        <p className="text-sm text-gray-500 mt-4">
          After enabling permissions, refresh the page to continue.
        </p>
      </div>
    );
  }

  // Request permission prompt
  return (
    <div className="flex flex-col items-center justify-center min-h-64 p-8 text-center">
      <div className="bg-blue-100 rounded-full p-4 mb-4">
        <svg
          className="w-8 h-8 text-blue-600"
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
      <h2 className="text-xl font-semibold text-gray-900 mb-2">{title}</h2>
      <p className="text-gray-600 mb-6 max-w-md">{description}</p>

      {requestError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 max-w-md">
          <p className="text-sm text-red-700">{requestError}</p>
        </div>
      )}

      <button
        onClick={handleRequestPermissions}
        disabled={isRequesting}
        className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium px-6 py-3 rounded-lg transition-colors flex items-center gap-2"
      >
        {isRequesting ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            Requesting Access...
          </>
        ) : (
          <>
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            Enable Camera & Microphone
          </>
        )}
      </button>

      <p className="text-sm text-gray-500 mt-4 max-w-sm">
        Your camera feed will be recorded during the assessment for instructor
        review.
      </p>
    </div>
  );
}

export default PermissionGate;
