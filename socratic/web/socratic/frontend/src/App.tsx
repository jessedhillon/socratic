import React from 'react';
import { Routes, Route } from 'react-router-dom';
import InstructorLayout from './components/InstructorLayout';
import AssessmentPage from './pages/AssessmentPage';
import AssignmentsPage from './pages/AssignmentsPage';
import AttemptHistoryPage from './pages/AttemptHistoryPage';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';
import ObjectivesPage from './pages/ObjectivesPage';
import ObjectiveViewPage from './pages/ObjectiveViewPage';
import ReviewPage from './pages/ReviewPage';

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        {/* Authentication routes */}
        <Route path="/:orgSlug/:role" element={<LoginPage />} />

        {/* Learner routes */}
        <Route path="/" element={<DashboardPage />} />
        <Route path="/history" element={<AttemptHistoryPage />} />
        <Route path="/assessment/:assignmentId" element={<AssessmentPage />} />
        <Route
          path="/assessment/:assignmentId/attempt/:attemptId"
          element={<AssessmentPage />}
        />

        {/* Instructor routes */}
        <Route element={<InstructorLayout />}>
          <Route path="/reviews" element={<ReviewPage />} />
          <Route path="/reviews/:attemptId" element={<ReviewPage />} />
          <Route path="/objectives" element={<ObjectivesPage />} />
          <Route
            path="/objectives/:objectiveId"
            element={<ObjectiveViewPage />}
          />
          <Route path="/assignments" element={<AssignmentsPage />} />
        </Route>
      </Routes>
    </div>
  );
};

export default App;
