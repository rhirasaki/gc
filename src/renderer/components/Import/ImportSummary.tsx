import React from 'react';

interface ImportSummaryProps {
  processed: number;
  errors: string[];
  onClose: () => void;
}

const ImportSummary: React.FC<ImportSummaryProps> = ({ processed, errors, onClose }) => {
  return (
    <div className="space-y-4">
      {/* Success */}
      <div className="flex items-center gap-3 p-4 bg-green-900/20 border border-green-800/50 rounded-lg">
        <div className="w-10 h-10 bg-green-600/20 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <div className="text-green-400 font-medium">Import Complete</div>
          <div className="text-sm text-gray-400">{processed} photo{processed !== 1 ? 's' : ''} imported successfully</div>
        </div>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-lg">
          <div className="text-red-400 font-medium mb-2">{errors.length} error{errors.length !== 1 ? 's' : ''}</div>
          <ul className="space-y-1 max-h-32 overflow-y-auto">
            {errors.map((err, i) => (
              <li key={i} className="text-xs text-red-300 font-mono">{err}</li>
            ))}
          </ul>
        </div>
      )}

      <button onClick={onClose} className="btn-primary w-full">
        Done
      </button>
    </div>
  );
};

export default ImportSummary;
