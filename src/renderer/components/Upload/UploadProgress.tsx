import React from 'react';
import { useUploadProgress } from '../../hooks/useUpload';

const UploadProgress: React.FC = () => {
  const progressItems = useUploadProgress();

  if (progressItems.length === 0) return null;

  return (
    <div className="card">
      <h3 className="text-white font-medium mb-3">Active Transfers</h3>
      <div className="space-y-3 max-h-64 overflow-y-auto">
        {progressItems.map((item) => (
          <div key={item.imageId} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-300 truncate max-w-xs font-mono">{item.filename}</span>
              <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                {item.status === 'uploading' && (
                  <span className="text-blue-400">{item.percentage}%</span>
                )}
                {item.status === 'done' && (
                  <span className="text-green-400 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Done
                  </span>
                )}
                {item.status === 'failed' && (
                  <span className="text-red-400 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Failed
                  </span>
                )}
              </div>
            </div>
            {item.status === 'uploading' && (
              <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-300"
                  style={{ width: `${item.percentage}%` }}
                />
              </div>
            )}
            {item.error && (
              <div className="text-xs text-red-400">{item.error}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default UploadProgress;
