import React, { useState } from 'react';
import { useUploadStatus, useUploadStart, useUploadControls } from '../../hooks/useUpload';
import { useSettings } from '../../hooks/useSettings';
import UploadProgress from './UploadProgress';

const UploadQueue: React.FC = () => {
  const { data: status, isLoading } = useUploadStatus();
  const { data: settings } = useSettings();
  const uploadStart = useUploadStart();
  const { pause, resume } = useUploadControls();
  const [isPaused, setIsPaused] = useState(false);

  const handleStart = async () => {
    if (!settings) return;
    await uploadStart.mutateAsync({
      remote: settings.rcloneRemote || 'gdrive',
      remotePath: settings.rcloneRemotePath || 'Photos',
      rclonePath: settings.rclonePath || 'rclone',
    });
  };

  const handlePause = async () => {
    await pause();
    setIsPaused(true);
  };

  const handleResume = async () => {
    await resume();
    setIsPaused(false);
  };

  return (
    <div className="space-y-6">
      {/* Status cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card">
          <div className="text-3xl font-bold text-white">{status?.queued ?? 0}</div>
          <div className="text-sm text-gray-500 mt-1">Queued</div>
        </div>
        <div className="card">
          <div className="text-3xl font-bold text-green-400">{status?.uploaded ?? 0}</div>
          <div className="text-sm text-gray-500 mt-1">Uploaded</div>
        </div>
        <div className="card">
          <div className="text-3xl font-bold text-red-400">{status?.failed ?? 0}</div>
          <div className="text-sm text-gray-500 mt-1">Failed</div>
        </div>
      </div>

      {/* Controls */}
      <div className="card">
        <h3 className="text-white font-medium mb-4">Upload Control</h3>
        <div className="flex items-center gap-3">
          {!status?.inProgress ? (
            <button
              onClick={handleStart}
              disabled={uploadStart.isPending}
              className="btn-primary flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              {uploadStart.isPending ? 'Starting...' : 'Start Upload'}
            </button>
          ) : (
            <>
              {!isPaused ? (
                <button onClick={handlePause} className="btn-secondary flex items-center gap-2">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                  </svg>
                  Pause
                </button>
              ) : (
                <button onClick={handleResume} className="btn-primary flex items-center gap-2">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  Resume
                </button>
              )}
            </>
          )}
        </div>

        {status?.inProgress && (
          <div className="mt-3 flex items-center gap-2 text-sm text-blue-400">
            <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            Upload in progress...
          </div>
        )}
      </div>

      {/* Cloud destination info */}
      {settings && (
        <div className="card">
          <h3 className="text-white font-medium mb-3">Destination</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-3">
              <span className="text-gray-500 w-20">Remote:</span>
              <span className="text-gray-300 font-mono">{settings.rcloneRemote || 'Not configured'}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-gray-500 w-20">Path:</span>
              <span className="text-gray-300 font-mono">{settings.rcloneRemotePath || 'Not configured'}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-gray-500 w-20">rclone:</span>
              <span className="text-gray-300 font-mono">{settings.rclonePath || 'rclone'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Live progress */}
      <UploadProgress />
    </div>
  );
};

export default UploadQueue;
