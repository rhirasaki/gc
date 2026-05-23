import React from 'react';
import ExportBuilder from '../components/Export/ExportBuilder';

const ExportPage: React.FC = () => {
  return (
    <div className="p-6 overflow-y-auto h-full">
      <p className="text-gray-500 text-sm mb-6 max-w-xl">
        Export your photo metadata to CSV. Filter by album, trip, date range, or file type.
        The export includes all EXIF data and file information.
      </p>
      <ExportBuilder />
    </div>
  );
};

export default ExportPage;
