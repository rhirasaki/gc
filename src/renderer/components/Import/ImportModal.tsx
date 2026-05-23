import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ScannedFile } from '../../types';
import ImportProgress from './ImportProgress';
import ImportSummary from './ImportSummary';
import { formatFileSize } from '../../hooks/useImages';

interface ImportModalProps {
  onClose: () => void;
}

type Step = 'select' | 'scanning' | 'review' | 'importing' | 'done';

interface ScanProgress {
  total: number;
  processed: number;
  currentFile: string;
}

interface ConfirmProgress {
  total: number;
  processed: number;
  currentFile: string;
}

const ImportModal: React.FC<ImportModalProps> = ({ onClose }) => {
  const [step, setStep] = useState<Step>('select');
  const [sourceDir, setSourceDir] = useState('');
  const [destDir, setDestDir] = useState('');
  const [scannedFiles, setScannedFiles] = useState<ScannedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [scanProgress, setScanProgress] = useState<ScanProgress>({ total: 0, processed: 0, currentFile: '' });
  const [importProgress, setImportProgress] = useState<ConfirmProgress>({ total: 0, processed: 0, currentFile: '' });
  const [importResult, setImportResult] = useState<{ processed: number; errors: string[] } | null>(null);
  const [deleteFromSD, setDeleteFromSD] = useState(false);
  const [rawOnly, setRawOnly] = useState(false);

  const queryClient = useQueryClient();

  useEffect(() => {
    const unsubScan = window.electronAPI.onImportScanProgress((progress) => {
      setScanProgress(progress);
    });
    const unsubConfirm = window.electronAPI.onImportConfirmProgress((progress) => {
      setImportProgress(progress);
    });
    return () => { unsubScan(); unsubConfirm(); };
  }, []);

  const handleSelectSource = async () => {
    const dir = await window.electronAPI.selectDirectory();
    if (dir) setSourceDir(dir);
  };

  const handleSelectDest = async () => {
    const dir = await window.electronAPI.selectDirectory();
    if (dir) setDestDir(dir);
  };

  const handleScan = async () => {
    if (!sourceDir) return;
    setStep('scanning');
    setScanProgress({ total: 0, processed: 0, currentFile: '' });

    try {
      const result = await window.electronAPI.importScan(sourceDir);
      if (result.success && result.files) {
        let files = result.files;
        if (rawOnly) {
          files = files.filter((f) => f.fileType === 'RAW');
        }
        setScannedFiles(files);
        setSelectedFiles(new Set(files.map((f) => f.filepath)));
        setStep('review');
      } else {
        alert(`Scan failed: ${result.error}`);
        setStep('select');
      }
    } catch (err) {
      alert(`Error scanning: ${err}`);
      setStep('select');
    }
  };

  const handleImport = async () => {
    if (!destDir) {
      alert('Please select a destination directory.');
      return;
    }

    const filesToImport = scannedFiles.filter((f) => selectedFiles.has(f.filepath));
    setStep('importing');
    setImportProgress({ total: filesToImport.length, processed: 0, currentFile: '' });

    try {
      const result = await window.electronAPI.importConfirm({
        files: filesToImport,
        destinationDir: destDir,
      });

      if (deleteFromSD) {
        await window.electronAPI.importDeleteFromSD(filesToImport.map((f) => f.filepath));
      }

      setImportResult({ processed: result.processed, errors: result.errors });
      queryClient.invalidateQueries({ queryKey: ['images'] });
      queryClient.invalidateQueries({ queryKey: ['analytics'] });
      setStep('done');
    } catch (err) {
      alert(`Import failed: ${err}`);
      setStep('review');
    }
  };

  const toggleFileSelection = (filepath: string) => {
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filepath)) next.delete(filepath);
      else next.add(filepath);
      return next;
    });
  };

  const rawCount = scannedFiles.filter((f) => f.fileType === 'RAW').length;
  const jpgCount = scannedFiles.filter((f) => f.fileType === 'JPG').length;
  const selectedCount = selectedFiles.size;

  return (
    <div className="fixed inset-0 z-40 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800">
          <h2 className="text-white font-semibold text-lg">Import Photos</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-6">
          {/* Step: Select */}
          {step === 'select' && (
            <div className="space-y-5">
              {/* Source */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Source Directory</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={sourceDir}
                    onChange={(e) => setSourceDir(e.target.value)}
                    placeholder="/Volumes/SD_CARD/DCIM"
                    className="input-field text-sm"
                  />
                  <button onClick={handleSelectSource} className="btn-secondary text-sm whitespace-nowrap px-3">
                    Browse
                  </button>
                </div>
              </div>

              {/* Destination */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Destination Directory</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={destDir}
                    onChange={(e) => setDestDir(e.target.value)}
                    placeholder="/Users/me/Photos/Library"
                    className="input-field text-sm"
                  />
                  <button onClick={handleSelectDest} className="btn-secondary text-sm whitespace-nowrap px-3">
                    Browse
                  </button>
                </div>
              </div>

              {/* Options */}
              <div className="space-y-2">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rawOnly}
                    onChange={(e) => setRawOnly(e.target.checked)}
                    className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-blue-600"
                  />
                  <span className="text-sm text-gray-300">Import RAW files only</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={deleteFromSD}
                    onChange={(e) => setDeleteFromSD(e.target.checked)}
                    className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-blue-600"
                  />
                  <span className="text-sm text-gray-300">Delete from source after import</span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button onClick={onClose} className="btn-ghost">Cancel</button>
                <button
                  onClick={handleScan}
                  disabled={!sourceDir}
                  className="btn-primary"
                >
                  Scan Directory
                </button>
              </div>
            </div>
          )}

          {/* Step: Scanning */}
          {step === 'scanning' && (
            <ImportProgress
              phase="scanning"
              current={scanProgress.processed}
              total={scanProgress.total}
              currentFile={scanProgress.currentFile}
            />
          )}

          {/* Step: Review */}
          {step === 'review' && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-3">
                <div className="card text-center">
                  <div className="text-2xl font-bold text-white">{scannedFiles.length}</div>
                  <div className="text-xs text-gray-500 mt-1">Total Files</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-amber-400">{rawCount}</div>
                  <div className="text-xs text-gray-500 mt-1">RAW Files</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-blue-400">{jpgCount}</div>
                  <div className="text-xs text-gray-500 mt-1">JPG Files</div>
                </div>
              </div>

              {/* File list */}
              <div className="border border-gray-800 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
                  <span className="text-xs text-gray-400">{selectedCount} of {scannedFiles.length} selected</span>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setSelectedFiles(new Set(scannedFiles.map((f) => f.filepath)))}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      Select All
                    </button>
                    <button
                      onClick={() => setSelectedFiles(new Set())}
                      className="text-xs text-gray-400 hover:text-white"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>
                <div className="max-h-64 overflow-y-auto divide-y divide-gray-800">
                  {scannedFiles.slice(0, 200).map((file) => (
                    <label
                      key={file.filepath}
                      className="flex items-center gap-3 px-4 py-2 hover:bg-gray-800/50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedFiles.has(file.filepath)}
                        onChange={() => toggleFileSelection(file.filepath)}
                        className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-blue-600"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-white truncate font-mono">{file.filename}</div>
                        <div className="text-xs text-gray-500">{formatFileSize(file.fileSize)}</div>
                      </div>
                      <span className={file.fileType === 'RAW' ? 'badge-raw' : 'badge-jpg'}>
                        {file.fileType}
                      </span>
                    </label>
                  ))}
                  {scannedFiles.length > 200 && (
                    <div className="px-4 py-2 text-xs text-gray-500 text-center">
                      + {scannedFiles.length - 200} more files
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-between gap-3">
                <button onClick={() => setStep('select')} className="btn-ghost">Back</button>
                <button
                  onClick={handleImport}
                  disabled={selectedCount === 0}
                  className="btn-primary"
                >
                  Import {selectedCount} File{selectedCount !== 1 ? 's' : ''}
                </button>
              </div>
            </div>
          )}

          {/* Step: Importing */}
          {step === 'importing' && (
            <ImportProgress
              phase="importing"
              current={importProgress.processed}
              total={importProgress.total}
              currentFile={importProgress.currentFile}
            />
          )}

          {/* Step: Done */}
          {step === 'done' && importResult && (
            <ImportSummary
              processed={importResult.processed}
              errors={importResult.errors}
              onClose={onClose}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default ImportModal;
