import { useCallback, useEffect } from 'react';
import { useBlocker } from 'react-router';

/**
 * Options for the navigation guard hook.
 */
export interface UseNavigationGuardOptions {
  /** Whether navigation should be blocked */
  shouldBlock: boolean;
  /** Message to show in the confirmation dialog */
  message?: string;
}

/**
 * Return value from the navigation guard hook.
 */
export interface UseNavigationGuardResult {
  /** Whether a navigation attempt is currently blocked */
  isBlocked: boolean;
  /** Proceed with the blocked navigation */
  proceed: () => void;
  /** Cancel the blocked navigation */
  cancel: () => void;
}

/**
 * Hook for blocking navigation with a confirmation dialog.
 *
 * Handles both:
 * - React Router navigation (back button, link clicks, programmatic navigation)
 * - Browser events (tab close, page refresh, browser back button)
 *
 * @example
 * ```tsx
 * function AssessmentPage() {
 *   const isRecording = sessionState === 'recording';
 *   const { isBlocked, proceed, cancel } = useNavigationGuard({
 *     shouldBlock: isRecording,
 *     message: 'Your recording will be stopped if you leave.',
 *   });
 *
 *   return (
 *     <>
 *       <AssessmentContent />
 *       {isBlocked && (
 *         <ConfirmDialog
 *           onConfirm={proceed}
 *           onCancel={cancel}
 *         />
 *       )}
 *     </>
 *   );
 * }
 * ```
 */
export function useNavigationGuard(
  options: UseNavigationGuardOptions
): UseNavigationGuardResult {
  const { shouldBlock, message = 'Are you sure you want to leave?' } = options;

  // Use react-router's useBlocker for SPA navigation
  const blocker = useBlocker(
    useCallback(
      ({ currentLocation, nextLocation }) => {
        // Only block if shouldBlock is true and we're actually navigating away
        return (
          shouldBlock && currentLocation.pathname !== nextLocation.pathname
        );
      },
      [shouldBlock]
    )
  );

  // Handle browser close/refresh via beforeunload
  useEffect(() => {
    if (!shouldBlock) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Modern browsers ignore custom messages, but we set it anyway
      e.returnValue = message;
      return message;
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [shouldBlock, message]);

  const proceed = useCallback(() => {
    if (blocker.state === 'blocked') {
      blocker.proceed();
    }
  }, [blocker]);

  const cancel = useCallback(() => {
    if (blocker.state === 'blocked') {
      blocker.reset();
    }
  }, [blocker]);

  return {
    isBlocked: blocker.state === 'blocked',
    proceed,
    cancel,
  };
}

export default useNavigationGuard;
