import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import LibraryPage from './pages/LibraryPage';
import HeatmapPage from './pages/HeatmapPage';
import UploadPage from './pages/UploadPage';
import ExportPage from './pages/ExportPage';
import AnalyticsPage from './pages/AnalyticsPage';
import TripsPage from './pages/TripsPage';
import SettingsPage from './pages/SettingsPage';

const App: React.FC = () => {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/library" replace />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/trips" element={<TripsPage />} />
        <Route path="/heatmap" element={<HeatmapPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  );
};

export default App;
