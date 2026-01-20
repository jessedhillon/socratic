import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Layouts
import InstructorLayout from './components/InstructorLayout';
import LearnerLayout from './components/LearnerLayout';

// Shared pages
import LoginPage from './pages/LoginPage';

// Learner pages
import LearnerDashboardPage from './pages/learner/DashboardPage';
import AssignmentDetailPage from './pages/learner/AssignmentDetailPage';
import LearnerAssessmentPage from './pages/learner/AssessmentPage';
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

const App: React.FC = () => {
  return (
    <Routes>
      {/* Dev test routes - no auth required */}
      <Route path="/dev/chat-test" element={<DevChatTestPage />} />
      <Route path="/dev/api-test" element={<DevApiTestPage />} />
      <Route path="/dev/av-test" element={<DevAvTestPage />} />

      {/* Authentication routes */}
      <Route path="/:orgSlug/:role" element={<LoginPage />} />

      {/* Learner routes - protected by LearnerLayout */}
      <Route element={<LearnerLayout />}>
        {/* Redirect root to assignments */}
        <Route path="/" element={<Navigate to="/assignments" replace />} />

        {/* Assignments */}
        <Route path="/assignments" element={<LearnerDashboardPage />} />
        <Route
          path="/assignments/:assignmentId"
          element={<AssignmentDetailPage />}
        />

        {/* Assessments - full-screen assessment experience */}
        <Route
          path="/assessments/:assignmentId"
          element={<LearnerAssessmentPage />}
        />

        {/* History */}
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:attemptId" element={<AttemptDetailPage />} />
      </Route>

      {/* Instructor routes - protected by InstructorLayout */}
      <Route element={<InstructorLayout />}>
        <Route path="/reviews" element={<ReviewPage />} />
        <Route path="/reviews/:attemptId" element={<ReviewPage />} />
        <Route path="/objectives" element={<ObjectivesPage />} />
        <Route
          path="/objectives/:objectiveId"
          element={<ObjectiveViewPage />}
        />
        <Route path="/instructor/assignments" element={<AssignmentsPage />} />
      </Route>

      {/* 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};

export default App;
