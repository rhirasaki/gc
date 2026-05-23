import React, { useState } from 'react';
import { useAlbums, useTrips } from '../../hooks/useAlbums';
import { FileTypeFilter } from '../../types';

interface ExportForm {
  albumId: string;
  tripId: string;
  startDate: string;
  endDate: string;
  fileType: FileTypeFilter;
}

const ExportBuilder: React.FC = () => {
  const [form, setForm] = useState<ExportForm>({
    albumId: '',
    tripId: '',
    startDate: '',
    endDate: '',
    fileType: 'ALL',
  });
  const [isExporting, setIsExporting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; rowsExported?: number; outputPath?: string; error?: string } | null>(null);

  const { data: albums } = useAlbums();
  const { data: trips } = useTrips();

  const handleExport = async () => {
    setIsExporting(true);
    setResult(null);

    try {
      const result = await window.electronAPI.exportCsv({
        albumId: form.albumId ? Number(form.albumId) : undefined,
        tripId: form.tripId ? Number(form.tripId) : undefined,
        startDate: form.startDate || undefined,
        endDate: form.endDate || undefined,
        fileType: form.fileType !== 'ALL' ? form.fileType : undefined,
      });
      setResult(result);
    } catch (err) {
      setResult({ success: false, error: String(err) });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="max-w-xl space-y-6">
      <div className="card space-y-4">
        <h3 className="text-white font-medium">Export Filters</h3>

        {/* Album filter */}
        <div>
          <label className="block text-sm text-gray-400 mb-1.5">Album</label>
          <select
            value={form.albumId}
            onChange={(e) => setForm((f) => ({ ...f, albumId: e.target.value }))}
            className="select-field text-sm"
          >
            <option value="">All Albums</option>
            {albums?.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        {/* Trip filter */}
        <div>
          <label className="block text-sm text-gray-400 mb-1.5">Trip</label>
          <select
            value={form.tripId}
            onChange={(e) => setForm((f) => ({ ...f, tripId: e.target.value }))}
            className="select-field text-sm"
          >
            <option value="">All Trips</option>
            {trips?.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Start Date</label>
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((f) => ({ ...f, startDate: e.target.value }))}
              className="input-field text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">End Date</label>
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((f) => ({ ...f, endDate: e.target.value }))}
              className="input-field text-sm"
            />
          </div>
        </div>

        {/* File type */}
        <div>
          <label className="block text-sm text-gray-400 mb-1.5">File Type</label>
          <div className="flex rounded-lg overflow-hidden border border-gray-700">
            {(['ALL', 'RAW', 'JPG'] as FileTypeFilter[]).map((type) => (
              <button
                key={type}
                onClick={() => setForm((f) => ({ ...f, fileType: type }))}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  form.fileType === type
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* CSV format info */}
      <div className="card">
        <h3 className="text-white font-medium mb-3">Export Format</h3>
        <div className="text-sm text-gray-400 space-y-1">
          <p>The CSV will include the following columns:</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {['filename', 'filepath', 'file_type', 'file_size', 'camera_model', 'iso', 'aperture', 'shutter_speed', 'focal_length', 'date_taken', 'latitude', 'longitude', 'albums', 'flags'].map((col) => (
              <span key={col} className="text-xs font-mono px-2 py-0.5 bg-gray-800 text-gray-300 rounded">
                {col}
              </span>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={handleExport}
        disabled={isExporting}
        className="btn-primary flex items-center gap-2"
      >
        {isExporting ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Exporting...
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export to CSV
          </>
        )}
      </button>

      {result && (
        <div className={`p-4 rounded-lg border ${
          result.success
            ? 'bg-green-900/20 border-green-800/50'
            : 'bg-red-900/20 border-red-800/50'
        }`}>
          {result.success ? (
            <div>
              <div className="text-green-400 font-medium">Export Complete</div>
              <div className="text-sm text-gray-400 mt-1">
                {result.rowsExported} rows exported to:
              </div>
              <div className="text-xs text-gray-300 font-mono mt-1 break-all">{result.outputPath}</div>
            </div>
          ) : (
            <div>
              <div className="text-red-400 font-medium">Export Failed</div>
              <div className="text-sm text-red-300 mt-1">{result.error}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ExportBuilder;
