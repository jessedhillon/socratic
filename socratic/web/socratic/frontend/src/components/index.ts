// Re-export components used across the app
export { CameraPreview, type CameraPreviewProps } from './CameraPreview';
export { PermissionGate } from './PermissionGate';
export {
  RecordingStatusOverlay,
  type RecordingStatusOverlayProps,
} from './RecordingStatusOverlay';
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

// Survey components
export { default as SurveyForm } from './SurveyForm';
