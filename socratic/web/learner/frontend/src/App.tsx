import React from 'react';
import { Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        {/* Authentication routes */}
        <Route path="/:orgSlug/:role" element={<LoginPage />} />

        {/* Learner routes */}
        <Route path="/" element={<DashboardPage />} />
      </Routes>
    </div>
  );
};

export default App;
