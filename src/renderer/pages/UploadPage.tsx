import React from 'react';
import UploadQueue from '../components/Upload/UploadQueue';

const UploadPage: React.FC = () => {
  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-2xl">
        <p className="text-gray-500 text-sm mb-6">
          Upload your photos to Google Drive or any rclone-compatible cloud storage.
          Configure your rclone remote in Settings before uploading.
        </p>
        <UploadQueue />
      </div>
    </div>
  );
};

export default UploadPage;
