/**
 * LiveKit API functions.
 *
 * These functions interact with the LiveKit-related backend endpoints.
 * Note: These are manually defined until the API client is regenerated.
 */

import { client } from './client.gen';

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
  const response = await client.POST('/api/livekit/rooms/{attempt_id}/token', {
    params: {
      path: { attempt_id: attemptId },
    },
  });

  if (response.error) {
    throw new Error(
      (response.error as LiveKitRoomTokenError).detail ||
        'Failed to get room token'
    );
  }

  return response.data as LiveKitRoomTokenResponse;
}
