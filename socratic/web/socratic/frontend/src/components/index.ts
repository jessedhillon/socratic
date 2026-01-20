// Re-export components used across the app
export { CameraPreview, type CameraPreviewProps } from './CameraPreview';
export { PermissionGate } from './PermissionGate';
export {
  default as SynchronizedPlayback,
  type WordTiming,
} from './SynchronizedPlayback';

// Re-export assessment components
export {
  ChatInterface,
  ChatMessage,
  type ChatMessageData,
  SpeakButton,
  VoiceInput,
} from './assessment';
