import React from 'react';

interface ImportProgressProps {
  phase: 'scanning' | 'importing';
  current: number;
  total: number;
  currentFile: string;
}

const ImportProgress: React.FC<ImportProgressProps> = ({ phase, current, total, currentFile }) => {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin flex-shrink-0" />
        <div className="flex-1">
          <div className="text-white font-medium">
            {phase === 'scanning' ? 'Scanning directory...' : 'Importing photos...'}
          </div>
          <div className="text-sm text-gray-400 truncate" title={currentFile}>
            {currentFile || 'Please wait...'}
          </div>
        </div>
      </div>

      {total > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{current} / {total} files</span>
            <span>{percentage}%</span>
          </div>
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-300"
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ImportProgress;
