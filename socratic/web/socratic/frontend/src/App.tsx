import React from 'react';
import { Routes, Route } from 'react-router-dom';
import AssessmentPage from './pages/AssessmentPage';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';
import ReviewPage from './pages/ReviewPage';

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        {/* Authentication routes */}
        <Route path="/:orgSlug/:role" element={<LoginPage />} />

        {/* Learner routes */}
        <Route path="/" element={<DashboardPage />} />
        <Route path="/assessment/:assignmentId" element={<AssessmentPage />} />
        <Route
          path="/assessment/:assignmentId/attempt/:attemptId"
          element={<AssessmentPage />}
        />

        {/* Educator routes */}
        <Route path="/reviews" element={<ReviewPage />} />
        <Route path="/reviews/:attemptId" element={<ReviewPage />} />
      </Routes>
    </div>
  );
};

export default App;
