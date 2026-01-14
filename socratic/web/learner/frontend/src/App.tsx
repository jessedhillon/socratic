import React from 'react';
import { Routes, Route } from 'react-router-dom';
import LearnerLayout from './components/LearnerLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import HistoryPage from './pages/HistoryPage';

const App: React.FC = () => {
  return (
    <Routes>
      {/* Authentication routes */}
      <Route path="/:orgSlug/:role" element={<LoginPage />} />

      {/* Learner routes - protected by LearnerLayout */}
      <Route element={<LearnerLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Route>
    </Routes>
  );
};

export default App;
