import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import LearnerLayout from './components/LearnerLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AssignmentDetailPage from './pages/AssignmentDetailPage';
import HistoryPage from './pages/HistoryPage';
import AttemptDetailPage from './pages/AttemptDetailPage';
import NotFoundPage from './pages/NotFoundPage';

const App: React.FC = () => {
  return (
    <Routes>
      {/* Authentication routes */}
      <Route path="/:orgSlug/:role" element={<LoginPage />} />

      {/* Learner routes - protected by LearnerLayout */}
      <Route element={<LearnerLayout />}>
        {/* Redirect root to assignments */}
        <Route path="/" element={<Navigate to="/assignments" replace />} />

        {/* Assignments */}
        <Route path="/assignments" element={<DashboardPage />} />
        <Route
          path="/assignments/:assignmentId"
          element={<AssignmentDetailPage />}
        />

        {/* History */}
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:attemptId" element={<AttemptDetailPage />} />

        {/* 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

export default App;
