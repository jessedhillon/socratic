/**
 * LiveKit API functions.
 *
 * These functions interact with the LiveKit-related backend endpoints.
 * Uses fetch directly since these endpoints aren't in the generated OpenAPI client yet.
 */

export interface LiveKitRoomTokenResponse {
  attempt_id: string;
  room_name: string;
  token: string;
  url: string;
}

export interface LiveKitRoomTokenError {
  detail: string;
}

/**
 * Get a LiveKit room token for joining an assessment voice session.
 *
 * @param attemptId - The assessment attempt ID
 * @returns Room token response with token, room name, and server URL
 */
export async function getLiveKitRoomToken(
  attemptId: string
): Promise<LiveKitRoomTokenResponse> {
  const response = await fetch(`/static/api/livekit/rooms/${attemptId}/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: 'Failed to get room token' }));
    throw new Error(error.detail || 'Failed to get room token');
  }

  return response.json() as Promise<LiveKitRoomTokenResponse>;
}

export interface StartLiveKitAssessmentResponse {
  attempt_id: string;
  assignment_id: string;
  objective_id: string;
  objective_title: string;
  room_name: string;
  token: string;
  url: string;
}

export interface StartLiveKitAssessmentError {
  detail: string;
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
  const response = await fetch(
    `/static/api/livekit/assessments/${assignmentId}/start`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: 'Failed to start assessment' }));
    throw new Error(error.detail || 'Failed to start LiveKit assessment');
  }

  return response.json() as Promise<StartLiveKitAssessmentResponse>;
}
