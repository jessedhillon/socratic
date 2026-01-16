import { useCallback, useEffect, useState } from 'react';

/**
 * Permission state for a media device.
 */
export type PermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';

/**
 * Combined permission status for camera and microphone.
 */
export interface MediaPermissionStatus {
  /** Camera permission state */
  camera: PermissionState;
  /** Microphone permission state */
  microphone: PermissionState;
  /** Whether both permissions are granted */
  allGranted: boolean;
  /** Whether either permission is denied */
  anyDenied: boolean;
  /** Whether the browser supports getUserMedia */
  isSupported: boolean;
  /** Whether permission query is in progress */
  isChecking: boolean;
}

/**
 * Result from the useMediaPermissions hook.
 */
export interface UseMediaPermissionsResult extends MediaPermissionStatus {
  /** Request camera and/or microphone permissions */
  requestPermissions: (options?: RequestOptions) => Promise<RequestResult>;
  /** Refresh the current permission states */
  refreshPermissions: () => Promise<void>;
  /** Get a user-friendly message for the current state */
  getStatusMessage: () => string;
  /** Get instructions for enabling permissions */
  getDeniedInstructions: () => string | null;
}

/**
 * Options for requesting permissions.
 */
export interface RequestOptions {
  /** Request camera permission (default: true) */
  camera?: boolean;
  /** Request microphone permission (default: true) */
  microphone?: boolean;
}

/**
 * Result from requesting permissions.
 */
export interface RequestResult {
  /** Whether the request was successful */
  success: boolean;
  /** Error message if failed */
  error: string | null;
  /** Error type for programmatic handling */
  errorType: 'none' | 'denied' | 'not_found' | 'not_supported' | 'unknown';
}

/**
 * Check if the browser supports getUserMedia.
 */
function isGetUserMediaSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'mediaDevices' in navigator &&
    'getUserMedia' in navigator.mediaDevices
  );
}

/**
 * Query the current permission state for a device type.
 * Falls back to 'prompt' if the Permissions API isn't available.
 */
async function queryPermission(
  name: 'camera' | 'microphone'
): Promise<PermissionState> {
  if (!isGetUserMediaSupported()) {
    return 'unavailable';
  }

  // Try the Permissions API first
  if ('permissions' in navigator) {
    try {
      const result = await navigator.permissions.query({
        name: name as PermissionName,
      });
      return result.state as PermissionState;
    } catch {
      // Permissions API doesn't support this query, fall back to 'prompt'
      return 'prompt';
    }
  }

  // No Permissions API, assume 'prompt' (will need to try getUserMedia)
  return 'prompt';
}

/**
 * Hook for managing camera and microphone permissions.
 *
 * Provides:
 * - Current permission state for camera and microphone
 * - Methods to request and refresh permissions
 * - User-friendly status messages and instructions
 * - Real-time permission state updates
 *
 * @example
 * ```tsx
 * function PermissionGate({ children }) {
 *   const {
 *     allGranted,
 *     anyDenied,
 *     isChecking,
 *     requestPermissions,
 *     getStatusMessage,
 *     getDeniedInstructions,
 *   } = useMediaPermissions();
 *
 *   if (isChecking) {
 *     return <div>Checking permissions...</div>;
 *   }
 *
 *   if (!allGranted) {
 *     return (
 *       <div>
 *         <p>{getStatusMessage()}</p>
 *         {anyDenied && <p>{getDeniedInstructions()}</p>}
 *         {!anyDenied && (
 *           <button onClick={() => requestPermissions()}>
 *             Enable Camera & Microphone
 *           </button>
 *         )}
 *       </div>
 *     );
 *   }
 *
 *   return children;
 * }
 * ```
 */
export function useMediaPermissions(): UseMediaPermissionsResult {
  const [camera, setCamera] = useState<PermissionState>('prompt');
  const [microphone, setMicrophone] = useState<PermissionState>('prompt');
  const [isChecking, setIsChecking] = useState(true);

  const isSupported = isGetUserMediaSupported();

  /**
   * Refresh the current permission states.
   */
  const refreshPermissions = useCallback(async () => {
    setIsChecking(true);
    try {
      const [cameraState, micState] = await Promise.all([
        queryPermission('camera'),
        queryPermission('microphone'),
      ]);
      setCamera(cameraState);
      setMicrophone(micState);
    } finally {
      setIsChecking(false);
    }
  }, []);

  // Check permissions on mount and set up listeners
  useEffect(() => {
    refreshPermissions();

    // Set up permission change listeners if available
    const listeners: Array<{
      permission: PermissionStatus;
      handler: () => void;
    }> = [];

    const setupListener = async (name: 'camera' | 'microphone') => {
      if ('permissions' in navigator) {
        try {
          const permission = await navigator.permissions.query({
            name: name as PermissionName,
          });
          const handler = () => {
            if (name === 'camera') {
              setCamera(permission.state as PermissionState);
            } else {
              setMicrophone(permission.state as PermissionState);
            }
          };
          permission.addEventListener('change', handler);
          listeners.push({ permission, handler });
        } catch {
          // Permissions API doesn't support this query
        }
      }
    };

    setupListener('camera');
    setupListener('microphone');

    return () => {
      for (const { permission, handler } of listeners) {
        permission.removeEventListener('change', handler);
      }
    };
  }, [refreshPermissions]);

  /**
   * Request camera and/or microphone permissions.
   */
  const requestPermissions = useCallback(
    async (options: RequestOptions = {}): Promise<RequestResult> => {
      const { camera: requestCamera = true, microphone: requestMic = true } =
        options;

      if (!isSupported) {
        return {
          success: false,
          error: 'Camera and microphone are not supported in this browser.',
          errorType: 'not_supported',
        };
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: requestCamera,
          audio: requestMic,
        });

        // Immediately stop all tracks - we only needed to verify permission
        // The actual stream will be acquired when recording starts
        stream.getTracks().forEach((track) => track.stop());

        // Update permission states
        if (requestCamera) setCamera('granted');
        if (requestMic) setMicrophone('granted');

        return {
          success: true,
          error: null,
          errorType: 'none',
        };
      } catch (err) {
        // Refresh to get accurate states
        await refreshPermissions();

        if (err instanceof DOMException) {
          if (err.name === 'NotAllowedError') {
            return {
              success: false,
              error:
                'Permission was denied. Please enable camera and microphone access.',
              errorType: 'denied',
            };
          } else if (err.name === 'NotFoundError') {
            return {
              success: false,
              error: 'No camera or microphone found. Please connect a device.',
              errorType: 'not_found',
            };
          }
        }

        return {
          success: false,
          error: err instanceof Error ? err.message : 'Unknown error occurred.',
          errorType: 'unknown',
        };
      }
    },
    [isSupported, refreshPermissions]
  );

  /**
   * Get a user-friendly message for the current permission state.
   */
  const getStatusMessage = useCallback((): string => {
    if (!isSupported) {
      return 'Your browser does not support camera and microphone access. Please use a modern browser like Chrome, Firefox, or Safari.';
    }

    if (camera === 'unavailable' || microphone === 'unavailable') {
      return 'Media devices are not available on this device.';
    }

    if (camera === 'denied' && microphone === 'denied') {
      return 'Camera and microphone access has been blocked.';
    }

    if (camera === 'denied') {
      return 'Camera access has been blocked.';
    }

    if (microphone === 'denied') {
      return 'Microphone access has been blocked.';
    }

    if (camera === 'granted' && microphone === 'granted') {
      return 'Camera and microphone are ready.';
    }

    if (camera === 'granted') {
      return 'Camera is ready. Microphone permission is needed.';
    }

    if (microphone === 'granted') {
      return 'Microphone is ready. Camera permission is needed.';
    }

    return 'Camera and microphone permission is needed to continue.';
  }, [isSupported, camera, microphone]);

  /**
   * Get instructions for enabling blocked permissions.
   */
  const getDeniedInstructions = useCallback((): string | null => {
    if (camera !== 'denied' && microphone !== 'denied') {
      return null;
    }

    // Detect browser for specific instructions
    const isChrome =
      /Chrome/.test(navigator.userAgent) && !/Edge/.test(navigator.userAgent);
    const isFirefox = /Firefox/.test(navigator.userAgent);
    const isSafari =
      /Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent);

    if (isChrome) {
      return 'Click the camera icon in the address bar, or go to Settings > Privacy and security > Site settings to enable access.';
    }

    if (isFirefox) {
      return 'Click the shield icon in the address bar and enable camera/microphone permissions, or go to about:preferences#privacy.';
    }

    if (isSafari) {
      return 'Go to Safari > Settings for This Website and allow camera and microphone access.';
    }

    return 'Check your browser settings to enable camera and microphone access for this site.';
  }, [camera, microphone]);

  const allGranted = camera === 'granted' && microphone === 'granted';
  const anyDenied = camera === 'denied' || microphone === 'denied';

  return {
    camera,
    microphone,
    allGranted,
    anyDenied,
    isSupported,
    isChecking,
    requestPermissions,
    refreshPermissions,
    getStatusMessage,
    getDeniedInstructions,
  };
}

export default useMediaPermissions;
