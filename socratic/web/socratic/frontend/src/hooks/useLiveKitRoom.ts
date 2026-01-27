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
  LocalTrackPublication,
  TrackPublication,
  Participant,
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
  /** Callback when receiving transcription data */
  onTranscription?: (
    text: string,
    isFinal: boolean,
    participantId: string
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
      publication: RemoteTrackPublication,
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
      publication: RemoteTrackPublication,
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

  // Handle data messages (for transcriptions)
  const handleDataReceived = useCallback(
    (payload: Uint8Array, participant?: RemoteParticipant) => {
      try {
        const text = new TextDecoder().decode(payload);
        const data = JSON.parse(text);

        if (data.type === 'transcription') {
          onTranscription?.(
            data.text,
            data.isFinal ?? true,
            participant?.identity ?? 'unknown'
          );
        }
      } catch (e) {
        // Not a JSON message or not a transcription, ignore
      }
    },
    [onTranscription]
  );

  // Connect to the room
  const connect = useCallback(async () => {
    if (roomRef.current?.state === ConnectionState.Connected) {
      return;
    }

    try {
      setError(null);
      updateConnectionState('connecting');

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      roomRef.current = room;

      // Set up event listeners
      room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.on(RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);
      room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakersChanged);
      room.on(RoomEvent.DataReceived, handleDataReceived);

      room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
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
    handleDataReceived,
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
