/**
 * Hook for connecting to and managing a LiveKit room for real-time voice assessments.
 *
 * Handles room connection, audio track management, and participant state.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Room,
  RoomEvent,
  ConnectionState,
  Track,
  RemoteParticipant,
  RemoteTrackPublication,
  Participant,
  type TranscriptionSegment,
  type TrackPublication,
} from 'livekit-client';

export type LiveKitConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

export interface UseLiveKitRoomOptions {
  /** LiveKit server URL */
  serverUrl: string;
  /** Access token for room connection */
  token: string;
  /** Whether to automatically connect on mount */
  autoConnect?: boolean;
  /** Callback when connection state changes */
  onConnectionStateChange?: (state: LiveKitConnectionState) => void;
  /** Callback when agent starts speaking */
  onAgentSpeakingChange?: (isSpeaking: boolean) => void;
  /** Callback when receiving transcription segments */
  onTranscription?: (
    segments: Array<{ id: string; text: string; isFinal: boolean }>,
    participantIdentity: string,
    isLocal: boolean
  ) => void;
}

export interface UseLiveKitRoomReturn {
  /** Current connection state */
  connectionState: LiveKitConnectionState;
  /** Whether the local microphone is enabled */
  isMicrophoneEnabled: boolean;
  /** Whether the agent is currently speaking */
  isAgentSpeaking: boolean;
  /** Error message if connection failed */
  error: string | null;
  /** Connect to the room */
  connect: () => Promise<void>;
  /** Disconnect from the room */
  disconnect: () => void;
  /** Toggle microphone on/off */
  toggleMicrophone: () => Promise<void>;
  /** Enable microphone */
  enableMicrophone: () => Promise<void>;
  /** Disable microphone */
  disableMicrophone: () => Promise<void>;
  /** The Room instance (for advanced usage) */
  room: Room | null;
}

/**
 * Hook for managing a LiveKit room connection.
 *
 * @example
 * ```tsx
 * const {
 *   connectionState,
 *   isMicrophoneEnabled,
 *   isAgentSpeaking,
 *   connect,
 *   disconnect,
 *   toggleMicrophone,
 * } = useLiveKitRoom({
 *   serverUrl: 'wss://your-livekit-server.com',
 *   token: 'your-access-token',
 *   onAgentSpeakingChange: (speaking) => console.log('Agent speaking:', speaking),
 * });
 * ```
 */
export function useLiveKitRoom(
  options: UseLiveKitRoomOptions
): UseLiveKitRoomReturn {
  const {
    serverUrl,
    token,
    autoConnect = false,
    onConnectionStateChange,
    onAgentSpeakingChange,
    onTranscription,
  } = options;

  const [connectionState, setConnectionState] =
    useState<LiveKitConnectionState>('disconnected');
  const [isMicrophoneEnabled, setIsMicrophoneEnabled] = useState(false);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roomRef = useRef<Room | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  // Update connection state and notify callback
  const updateConnectionState = useCallback(
    (state: LiveKitConnectionState) => {
      setConnectionState(state);
      onConnectionStateChange?.(state);
    },
    [onConnectionStateChange]
  );

  // Update agent speaking state and notify callback
  const updateAgentSpeaking = useCallback(
    (speaking: boolean) => {
      setIsAgentSpeaking(speaking);
      onAgentSpeakingChange?.(speaking);
    },
    [onAgentSpeakingChange]
  );

  // Handle audio track subscription
  const handleTrackSubscribed = useCallback(
    (
      track: Track,
      _publication: RemoteTrackPublication,
      participant: RemoteParticipant
    ) => {
      if (track.kind === Track.Kind.Audio) {
        // Create audio element for playback
        if (!audioElementRef.current) {
          audioElementRef.current = document.createElement('audio');
          audioElementRef.current.autoplay = true;
          document.body.appendChild(audioElementRef.current);
        }

        // Attach the track to the audio element
        track.attach(audioElementRef.current);
        console.log(`Subscribed to audio track from ${participant.identity}`);
      }
    },
    []
  );

  // Handle track unsubscription
  const handleTrackUnsubscribed = useCallback(
    (
      track: Track,
      _publication: RemoteTrackPublication,
      participant: RemoteParticipant
    ) => {
      if (track.kind === Track.Kind.Audio) {
        track.detach();
        console.log(
          `Unsubscribed from audio track from ${participant.identity}`
        );
      }
    },
    []
  );

  // Handle speaking state changes
  const handleActiveSpeakersChanged = useCallback(
    (speakers: Participant[]) => {
      // Check if any remote participant (the agent) is speaking
      const agentSpeaking = speakers.some(
        (speaker) => speaker instanceof RemoteParticipant
      );
      updateAgentSpeaking(agentSpeaking);
    },
    [updateAgentSpeaking]
  );

  // Handle transcription events from LiveKit
  const handleTranscriptionReceived = useCallback(
    (
      segments: TranscriptionSegment[],
      participant?: Participant,
      _publication?: TrackPublication
    ) => {
      if (!participant) return;

      const isLocal = !(participant instanceof RemoteParticipant);
      console.log(
        '[LiveKit transcription]',
        isLocal ? 'local' : 'remote',
        participant.identity,
        segments.map((s) => ({
          id: s.id,
          final: s.final,
          text: s.text.slice(0, 40),
        }))
      );
      onTranscription?.(
        segments.map((s) => ({ id: s.id, text: s.text, isFinal: s.final })),
        participant.identity,
        isLocal
      );
    },
    [onTranscription]
  );

  // Connect to the room
  const connect = useCallback(async () => {
    if (roomRef.current?.state === ConnectionState.Connected) {
      return;
    }

    let room: Room | null = null;

    try {
      setError(null);
      updateConnectionState('connecting');

      room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      roomRef.current = room;

      // Set up event listeners — guard against stale rooms so that
      // React StrictMode cleanup of a previous mount doesn't clobber
      // the state of the current mount's room.
      room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.on(RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);
      room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakersChanged);
      room.on(RoomEvent.TranscriptionReceived, handleTranscriptionReceived);

      const thisRoom = room;
      room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (roomRef.current !== thisRoom) return;
        switch (state) {
          case ConnectionState.Connected:
            updateConnectionState('connected');
            break;
          case ConnectionState.Reconnecting:
            updateConnectionState('reconnecting');
            break;
          case ConnectionState.Disconnected:
            updateConnectionState('disconnected');
            break;
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        if (roomRef.current !== thisRoom) return;
        updateConnectionState('disconnected');
        updateAgentSpeaking(false);
      });

      // Connect to the room
      await room.connect(serverUrl, token);

      // Enable microphone by default for voice assessments
      await room.localParticipant.setMicrophoneEnabled(true);
      setIsMicrophoneEnabled(true);

      updateConnectionState('connected');
    } catch (err) {
      // Only propagate errors from the current room. When React StrictMode
      // double-fires effects, the first mount's cleanup disconnects its room
      // and a new room is created for the second mount. We ignore connection
      // errors from the stale first room.
      if (room && roomRef.current !== room) {
        return;
      }
      const message = err instanceof Error ? err.message : 'Failed to connect';
      setError(message);
      updateConnectionState('error');
      console.error('LiveKit connection error:', err);
    }
  }, [
    serverUrl,
    token,
    updateConnectionState,
    updateAgentSpeaking,
    handleTrackSubscribed,
    handleTrackUnsubscribed,
    handleActiveSpeakersChanged,
    handleTranscriptionReceived,
  ]);

  // Disconnect from the room
  const disconnect = useCallback(() => {
    if (!roomRef.current && !audioElementRef.current) {
      return;
    }

    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }

    // Clean up audio element
    if (audioElementRef.current) {
      audioElementRef.current.remove();
      audioElementRef.current = null;
    }

    setIsMicrophoneEnabled(false);
    updateAgentSpeaking(false);
    updateConnectionState('disconnected');
  }, [updateConnectionState, updateAgentSpeaking]);

  // Toggle microphone
  const toggleMicrophone = useCallback(async () => {
    if (!roomRef.current) return;

    const newState = !isMicrophoneEnabled;
    await roomRef.current.localParticipant.setMicrophoneEnabled(newState);
    setIsMicrophoneEnabled(newState);
  }, [isMicrophoneEnabled]);

  // Enable microphone
  const enableMicrophone = useCallback(async () => {
    if (!roomRef.current || isMicrophoneEnabled) return;

    await roomRef.current.localParticipant.setMicrophoneEnabled(true);
    setIsMicrophoneEnabled(true);
  }, [isMicrophoneEnabled]);

  // Disable microphone
  const disableMicrophone = useCallback(async () => {
    if (!roomRef.current || !isMicrophoneEnabled) return;

    await roomRef.current.localParticipant.setMicrophoneEnabled(false);
    setIsMicrophoneEnabled(false);
  }, [isMicrophoneEnabled]);

  // Refs for connect/disconnect so the effect doesn't re-run on callback identity changes
  const connectRef = useRef(connect);
  connectRef.current = connect;
  const disconnectRef = useRef(disconnect);
  disconnectRef.current = disconnect;

  // Auto-connect and cleanup in a single effect
  useEffect(() => {
    if (autoConnect && token && serverUrl) {
      connectRef.current();
    }
    return () => {
      disconnectRef.current();
    };
  }, [autoConnect, token, serverUrl]);

  return {
    connectionState,
    isMicrophoneEnabled,
    isAgentSpeaking,
    error,
    connect,
    disconnect,
    toggleMicrophone,
    enableMicrophone,
    disableMicrophone,
    room: roomRef.current,
  };
}

export default useLiveKitRoom;
