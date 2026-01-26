/**
 * LiveKit API functions.
 *
 * Re-exports from the generated OpenAPI client with simplified interfaces.
 */

// Re-export the generated functions
export {
  getLivekitRoomToken,
  startLivekitAssessment,
  startRoomRecording,
  stopRoomRecording,
  getRoomRecording,
  listRoomRecordings,
} from './sdk.gen';

// Re-export the response types for convenience
export type {
  LiveKitRoomTokenResponse,
  StartLiveKitAssessmentResponse,
  StartRecordingResponse,
  StopRecordingResponse,
  EgressRecordingResponse,
} from './types.gen';

// Convenience wrapper functions with simpler interfaces

import {
  getLivekitRoomToken as _getLivekitRoomToken,
  startLivekitAssessment as _startLivekitAssessment,
} from './sdk.gen';
import type {
  LiveKitRoomTokenResponse,
  StartLiveKitAssessmentResponse,
} from './types.gen';

/**
 * Get a LiveKit room token for joining an assessment voice session.
 *
 * @param attemptId - The assessment attempt ID
 * @returns Room token response with token, room name, and server URL
 */
export async function getLiveKitRoomToken(
  attemptId: string
): Promise<LiveKitRoomTokenResponse> {
  const response = await _getLivekitRoomToken({
    path: { attempt_id: attemptId },
  });

  if (response.error) {
    throw new Error(
      (response.error as { detail?: string }).detail ||
        'Failed to get room token'
    );
  }

  return response.data as LiveKitRoomTokenResponse;
}

/**
 * Start a new LiveKit-based assessment.
 *
 * Creates an assessment attempt and a LiveKit room with assessment context.
 * Returns everything the frontend needs to connect and begin the real-time
 * voice assessment.
 *
 * @param assignmentId - The assignment ID to start the assessment for
 * @returns Assessment start response with attempt details and room credentials
 */
export async function startLiveKitAssessment(
  assignmentId: string
): Promise<StartLiveKitAssessmentResponse> {
  const response = await _startLivekitAssessment({
    path: { assignment_id: assignmentId },
  });

  if (response.error) {
    throw new Error(
      (response.error as { detail?: string }).detail ||
        'Failed to start LiveKit assessment'
    );
  }

  return response.data as StartLiveKitAssessmentResponse;
}
