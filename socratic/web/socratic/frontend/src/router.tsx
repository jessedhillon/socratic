import { createBrowserRouter, Navigate } from 'react-router-dom';

// Layouts
import InstructorLayout from './components/InstructorLayout';
import LearnerLayout from './components/LearnerLayout';

// Shared pages
import LoginPage from './pages/LoginPage';

// Learner pages
import LearnerDashboardPage from './pages/learner/DashboardPage';
import AssignmentDetailPage from './pages/learner/AssignmentDetailPage';
import LearnerAssessmentPage from './pages/learner/AssessmentPage';
import LiveKitAssessmentPage from './pages/learner/LiveKitAssessmentPage';
import HistoryPage from './pages/learner/HistoryPage';
import AttemptDetailPage from './pages/learner/AttemptDetailPage';
import NotFoundPage from './pages/learner/NotFoundPage';

// Instructor pages
import ReviewPage from './pages/ReviewPage';
import ObjectivesPage from './pages/ObjectivesPage';
import ObjectiveViewPage from './pages/ObjectiveViewPage';
import AssignmentsPage from './pages/AssignmentsPage';

// Dev test pages
import DevChatTestPage from './pages/dev/DevChatTestPage';
import DevApiTestPage from './pages/dev/DevApiTestPage';
import DevAvTestPage from './pages/dev/DevAvTestPage';
import DevLiveKitTestPage from './pages/dev/DevLiveKitTestPage';

export const router = createBrowserRouter(
  [
    // Dev test routes - no auth required
    {
      path: '/dev/chat-test',
      element: <DevChatTestPage />,
    },
    {
      path: '/dev/api-test',
      element: <DevApiTestPage />,
    },
    {
      path: '/dev/av-test',
      element: <DevAvTestPage />,
    },
    {
      path: '/dev/livekit-test',
      element: <DevLiveKitTestPage />,
    },

    // Authentication routes
    {
      path: '/:orgSlug/:role',
      element: <LoginPage />,
    },

    // Learner routes - protected by LearnerLayout
    {
      element: <LearnerLayout />,
      children: [
        // Redirect root to assignments
        {
          path: '/',
          element: <Navigate to="/assignments" replace />,
        },

        // Assignments
        {
          path: '/assignments',
          element: <LearnerDashboardPage />,
        },
        {
          path: '/assignments/:assignmentId',
          element: <AssignmentDetailPage />,
        },

        // Assessments - full-screen assessment experience
        {
          path: '/assessments/:assignmentId',
          element: <LearnerAssessmentPage />,
        },
        // LiveKit real-time voice assessments
        {
          path: '/assessments/:assignmentId/live',
          element: <LiveKitAssessmentPage />,
        },

        // History
        {
          path: '/history',
          element: <HistoryPage />,
        },
        {
          path: '/history/:attemptId',
          element: <AttemptDetailPage />,
        },
      ],
    },

    // Instructor routes - protected by InstructorLayout
    {
      element: <InstructorLayout />,
      children: [
        {
          path: '/reviews',
          element: <ReviewPage />,
        },
        {
          path: '/reviews/:attemptId',
          element: <ReviewPage />,
        },
        {
          path: '/objectives',
          element: <ObjectivesPage />,
        },
        {
          path: '/objectives/:objectiveId',
          element: <ObjectiveViewPage />,
        },
        {
          path: '/instructor/assignments',
          element: <AssignmentsPage />,
        },
      ],
    },

    // 404
    {
      path: '*',
      element: <NotFoundPage />,
    },
  ],
  {
    basename: '/static',
  }
);
