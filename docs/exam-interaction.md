# Exam Interaction Design

This document captures the design decisions for the examination interface where learners complete assessments.

## Assessment Flow

### End Condition

The assessment end is **AI-driven**, not time-limited. The assessment completes when:

1. All prompts have been explored
2. The learner's understanding has been fully assessed

The estimated duration shown to learners is a recommendation for pacing, not a hard limit. The AI uses it to gauge how deeply to probe and when to wrap up.

### Evaluation Timing

Evaluation is **batched and asynchronous**:

1. Learner completes assessment
2. AI generates evaluation (strengths, gaps, grade recommendation)
3. Evaluation goes to instructor review queue
4. Instructor reviews and approves/adjusts
5. Learner sees feedback only after instructor approval

This buffer prevents learners from seeing raw AI judgments and keeps instructors in the loop.

### Learner Visibility

- Learners do **not** see rubric criteria during the assessment
- Future enhancement: pre-assessment instructions displayed as markdown

## Integrity Mechanisms

### Voice Input (Primary)

Voice is not just a nice-to-have feature - it's the **primary integrity mechanism**.

Speaking responses prevents:

- Copy/paste to ChatGPT or other AI assistants
- Reading from prepared notes verbatim
- Having someone else type responses

The friction of speaking naturally exposes actual understanding.

### Video Recording (Secondary)

Video recording provides a **proctoring layer**:

- Continuous recording during assessment
- Stored for instructor review
- Instructor can check for signs of cheating:
  - Looking at other screens
  - Reading from notes
  - Another person present

### Instructor Review (Tertiary)

The instructor review step serves as a third integrity layer:

- Review AI evaluation for accuracy
- Optionally review video recordings
- Adjust grades or flag suspicious attempts

## Interaction Model

### Turn-Based, Not Real-Time

For the initial implementation, the interaction is **turn-based**:

1. AI presents a prompt (text + speech)
2. Learner responds verbally
3. AI processes response and presents next prompt
4. Repeat until assessment complete

Real-time conversational AI (interruptions, back-and-forth) is a future enhancement. Turn-based with video proctoring provides sufficient integrity for MVP.

### Dual Modality for AI Prompts

AI prompts are delivered in **both modalities**:

- **Text**: Displayed on screen for reference
- **Speech**: Read aloud via TTS

This ensures accessibility and accommodates different learning styles.

### Voice Input for Responses

Learner responses are captured via **speech-to-text**:

- Learner speaks their response
- STT converts to text for AI processing
- Original audio retained for review if needed

### Transcription Trust Boundary

The transcription flow must maintain a **server-side trust boundary**:

1. Client sends audio blob to server
2. Server transcribes via Whisper and **stores the result authoritatively**
3. Client receives transcription for read-only preview (not editable)
4. Assessment uses server-stored transcription, not client-submitted text

This prevents learners from:

- Editing transcriptions to fix spoken mistakes
- Pasting pre-written text from external sources
- Bypassing the voice requirement entirely

The client should never send free-form text that gets treated as "what the learner said." The only acceptable inputs are:

- Raw audio blobs (for transcription)
- References to already-stored transcriptions

Any text editing UI (if present) is for development/testing only and must not be used in production assessments.

## Technical Components

| Component | Purpose                  | Options                   |
| --------- | ------------------------ | ------------------------- |
| TTS       | AI prompt speech         | OpenAI TTS, ElevenLabs    |
| STT       | Learner response capture | OpenAI Whisper, Deepgram  |
| Video     | Proctoring recording     | Browser MediaRecorder API |
| Storage   | Media files              | S3                        |
| LLM       | Assessment logic         | Claude                    |

### Browser APIs

The exam interface relies on browser APIs:

- `MediaRecorder` for video/audio capture
- `getUserMedia` for camera/microphone access
- WebSocket or polling for turn-based communication

### Storage Considerations

Media files (video recordings, audio responses) should be:

- Stored in S3 with appropriate retention policies
- Linked to attempt records for instructor review
- Cleaned up after configurable retention period
