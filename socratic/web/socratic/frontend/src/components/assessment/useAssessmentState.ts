import { useReducer, useCallback } from 'react';
import type { ChatMessageData } from './ChatMessage';

/**
 * Assessment lifecycle states.
 */
export type AssessmentPhase =
  | 'idle' // Waiting to start
  | 'initializing' // Loading assignment, requesting permissions
  | 'ready' // Ready to begin (permissions granted)
  | 'in_progress' // Assessment active, turn-based interaction
  | 'closure_ready' // AI signaled completion, learner can still respond or finish
  | 'completing' // Wrapping up, final processing
  | 'completed' // Assessment finished
  | 'error'; // Recoverable error state

/**
 * Assessment state.
 */
export interface AssessmentState {
  phase: AssessmentPhase;
  attemptId: string | null;
  assignmentId: string | null;
  objectiveTitle: string | null;
  messages: ChatMessageData[];
  isWaitingForResponse: boolean;
  error: string | null;
  startedAt: string | null;
}

/**
 * Actions that can modify the assessment state.
 */
export type AssessmentAction =
  | { type: 'INITIALIZE'; assignmentId: string }
  | { type: 'PERMISSIONS_GRANTED' }
  | { type: 'START_ASSESSMENT'; attemptId: string; objectiveTitle: string }
  | { type: 'ADD_MESSAGE'; message: ChatMessageData }
  | { type: 'UPDATE_STREAMING_MESSAGE'; id: string; content: string }
  | { type: 'FINISH_STREAMING_MESSAGE'; id: string }
  | { type: 'SEND_MESSAGE'; content: string }
  | { type: 'RESPONSE_STARTED' }
  | { type: 'RESPONSE_COMPLETE' }
  | { type: 'CLOSURE_READY' } // AI signaled completion, learner can still respond
  | { type: 'CONTINUE_ASSESSMENT' } // Learner chose to continue after closure_ready
  | { type: 'ASSESSMENT_COMPLETING' }
  | { type: 'ASSESSMENT_COMPLETE' }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'RESET' }
  | { type: 'SET_MOCK_STATE'; state: Partial<AssessmentState> }; // For testing

const initialState: AssessmentState = {
  phase: 'idle',
  attemptId: null,
  assignmentId: null,
  objectiveTitle: null,
  messages: [],
  isWaitingForResponse: false,
  error: null,
  startedAt: null,
};

function generateMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Reducer for assessment state machine.
 */
function assessmentReducer(
  state: AssessmentState,
  action: AssessmentAction
): AssessmentState {
  switch (action.type) {
    case 'INITIALIZE':
      return {
        ...initialState,
        phase: 'initializing',
        assignmentId: action.assignmentId,
      };

    case 'PERMISSIONS_GRANTED':
      if (state.phase !== 'initializing') return state;
      return {
        ...state,
        phase: 'ready',
      };

    case 'START_ASSESSMENT':
      if (state.phase !== 'ready' && state.phase !== 'initializing')
        return state;
      return {
        ...state,
        phase: 'in_progress',
        attemptId: action.attemptId,
        objectiveTitle: action.objectiveTitle,
        startedAt: new Date().toISOString(),
        isWaitingForResponse: true,
      };

    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.message],
      };

    case 'UPDATE_STREAMING_MESSAGE': {
      const messages = state.messages.map((msg) =>
        msg.id === action.id
          ? { ...msg, content: action.content, isStreaming: true }
          : msg
      );
      return { ...state, messages };
    }

    case 'FINISH_STREAMING_MESSAGE': {
      const messages = state.messages.map((msg) =>
        msg.id === action.id ? { ...msg, isStreaming: false } : msg
      );
      return { ...state, messages };
    }

    case 'SEND_MESSAGE': {
      const learnerMessage: ChatMessageData = {
        id: generateMessageId(),
        type: 'learner',
        content: action.content,
        timestamp: new Date().toISOString(),
      };
      return {
        ...state,
        messages: [...state.messages, learnerMessage],
        isWaitingForResponse: true,
      };
    }

    case 'RESPONSE_STARTED':
      return {
        ...state,
        isWaitingForResponse: true,
      };

    case 'RESPONSE_COMPLETE':
      return {
        ...state,
        isWaitingForResponse: false,
      };

    case 'CLOSURE_READY':
      if (state.phase !== 'in_progress') return state;
      return {
        ...state,
        phase: 'closure_ready',
        isWaitingForResponse: false,
      };

    case 'CONTINUE_ASSESSMENT':
      if (state.phase !== 'closure_ready') return state;
      return {
        ...state,
        phase: 'in_progress',
      };

    case 'ASSESSMENT_COMPLETING':
      return {
        ...state,
        phase: 'completing',
        isWaitingForResponse: true,
      };

    case 'ASSESSMENT_COMPLETE':
      return {
        ...state,
        phase: 'completed',
        isWaitingForResponse: false,
      };

    case 'SET_ERROR':
      return {
        ...state,
        phase: 'error',
        error: action.error,
        isWaitingForResponse: false,
      };

    case 'CLEAR_ERROR':
      // Return to previous valid state
      return {
        ...state,
        phase: state.attemptId ? 'in_progress' : 'idle',
        error: null,
      };

    case 'RESET':
      return initialState;

    case 'SET_MOCK_STATE':
      // For testing - directly set state values
      return {
        ...state,
        ...action.state,
      };

    default:
      return state;
  }
}

/**
 * Hook for managing assessment state.
 *
 * Provides the state machine and action dispatchers for the assessment flow.
 */
export function useAssessmentState() {
  const [state, dispatch] = useReducer(assessmentReducer, initialState);

  const initialize = useCallback((assignmentId: string) => {
    dispatch({ type: 'INITIALIZE', assignmentId });
  }, []);

  const grantPermissions = useCallback(() => {
    dispatch({ type: 'PERMISSIONS_GRANTED' });
  }, []);

  const startAssessment = useCallback(
    (attemptId: string, objectiveTitle: string) => {
      dispatch({ type: 'START_ASSESSMENT', attemptId, objectiveTitle });
    },
    []
  );

  const addMessage = useCallback((message: ChatMessageData) => {
    dispatch({ type: 'ADD_MESSAGE', message });
  }, []);

  const addInterviewerMessage = useCallback(
    (content: string, isStreaming = false) => {
      const message: ChatMessageData = {
        id: generateMessageId(),
        type: 'interviewer',
        content,
        timestamp: new Date().toISOString(),
        isStreaming,
      };
      dispatch({ type: 'ADD_MESSAGE', message });
      return message.id;
    },
    []
  );

  const addSystemMessage = useCallback((content: string) => {
    const message: ChatMessageData = {
      id: generateMessageId(),
      type: 'system',
      content,
      timestamp: new Date().toISOString(),
    };
    dispatch({ type: 'ADD_MESSAGE', message });
    return message.id;
  }, []);

  const updateStreamingMessage = useCallback((id: string, content: string) => {
    dispatch({ type: 'UPDATE_STREAMING_MESSAGE', id, content });
  }, []);

  const finishStreamingMessage = useCallback((id: string) => {
    dispatch({ type: 'FINISH_STREAMING_MESSAGE', id });
  }, []);

  const sendMessage = useCallback((content: string) => {
    dispatch({ type: 'SEND_MESSAGE', content });
  }, []);

  const responseStarted = useCallback(() => {
    dispatch({ type: 'RESPONSE_STARTED' });
  }, []);

  const responseComplete = useCallback(() => {
    dispatch({ type: 'RESPONSE_COMPLETE' });
  }, []);

  const closureReady = useCallback(() => {
    dispatch({ type: 'CLOSURE_READY' });
  }, []);

  const continueAssessment = useCallback(() => {
    dispatch({ type: 'CONTINUE_ASSESSMENT' });
  }, []);

  const beginCompletion = useCallback(() => {
    dispatch({ type: 'ASSESSMENT_COMPLETING' });
  }, []);

  const completeAssessment = useCallback(() => {
    dispatch({ type: 'ASSESSMENT_COMPLETE' });
  }, []);

  const setMockState = useCallback((mockState: Partial<AssessmentState>) => {
    dispatch({ type: 'SET_MOCK_STATE', state: mockState });
  }, []);

  const setError = useCallback((error: string) => {
    dispatch({ type: 'SET_ERROR', error });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'CLEAR_ERROR' });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  return {
    state,
    actions: {
      initialize,
      grantPermissions,
      startAssessment,
      addMessage,
      addInterviewerMessage,
      addSystemMessage,
      updateStreamingMessage,
      finishStreamingMessage,
      sendMessage,
      responseStarted,
      responseComplete,
      closureReady,
      continueAssessment,
      beginCompletion,
      completeAssessment,
      setMockState,
      setError,
      clearError,
      reset,
    },
  };
}

export type AssessmentActions = ReturnType<
  typeof useAssessmentState
>['actions'];
