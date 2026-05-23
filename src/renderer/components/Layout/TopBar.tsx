import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import ImportModal from '../Import/ImportModal';

const pageTitles: Record<string, string> = {
  '/library': 'Photo Library',
  '/trips': 'Trips',
  '/heatmap': 'Photo Map',
  '/upload': 'Upload to Cloud',
  '/export': 'Export Data',
  '/analytics': 'Analytics',
  '/settings': 'Settings',
};

const TopBar: React.FC = () => {
  const location = useLocation();
  const [showImport, setShowImport] = useState(false);
  const title = pageTitles[location.pathname] || 'Photo Organizer';

  return (
    <>
      <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6 flex-shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-white font-semibold text-lg">{title}</h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Import Photos
          </button>
        </div>
      </header>

      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} />
      )}
    </>
  );
};

export default TopBar;
