import React, { useState, useEffect } from 'react';
import { useSettings, useUpdateSettings } from '../../hooks/useSettings';
import { AppSettings } from '../../types';

const SettingsPanel: React.FC = () => {
  const { data: settings, isLoading } = useSettings();
  const updateSettings = useUpdateSettings();
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setForm(settings);
    }
  }, [settings]);

  const handleSave = async () => {
    await updateSettings.mutateAsync(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleSelectDir = async (field: keyof AppSettings) => {
    const dir = await window.electronAPI.selectDirectory();
    if (dir) {
      setForm((f) => ({ ...f, [field]: dir }));
    }
  };

  const handleBackup = async () => {
    try {
      const result = await window.electronAPI.backupTrigger();
      alert(`Backup complete: ${result.success} succeeded, ${result.failed} failed`);
    } catch (err) {
      alert(`Backup failed: ${err}`);
    }
  };

  if (isLoading) {
    return <div className="p-6 text-gray-500">Loading settings...</div>;
  }

  return (
    <div className="p-6 overflow-y-auto h-full max-w-2xl space-y-6">
      {/* Library */}
      <div className="card space-y-4">
        <h3 className="text-white font-semibold">Photo Library</h3>
        <div>
          <label className="block text-sm text-gray-400 mb-1.5">Library Path</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={form.libraryPath ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, libraryPath: e.target.value }))}
              placeholder="/Users/me/Photos/Library"
              className="input-field text-sm"
            />
            <button
              onClick={() => handleSelectDir('libraryPath')}
              className="btn-secondary text-sm whitespace-nowrap px-3"
            >
              Browse
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1.5">Thumbnail Size (px)</label>
          <input
            type="number"
            value={form.thumbnailSize ?? 200}
            onChange={(e) => setForm((f) => ({ ...f, thumbnailSize: Number(e.target.value) }))}
            min="100"
            max="500"
            step="50"
            className="input-field text-sm w-32"
          />
        </div>
      </div>

      {/* Cloud upload */}
      <div className="card space-y-4">
        <h3 className="text-white font-semibold">Cloud Upload (rclone)</h3>

        <div>
          <label className="block text-sm text-gray-400 mb-1.5">rclone Executable Path</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={form.rclonePath ?? 'rclone'}
              onChange={(e) => setForm((f) => ({ ...f, rclonePath: e.target.value }))}
              placeholder="rclone"
              className="input-field text-sm"
            />
            <button
              onClick={() => window.electronAPI.selectFile([{ name: 'Executables', extensions: ['*'] }]).then((p) => p && setForm((f) => ({ ...f, rclonePath: p })))}
              className="btn-secondary text-sm whitespace-nowrap px-3"
            >
              Browse
            </button>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Leave as "rclone" if it is in your PATH
          </p>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1.5">Remote Name</label>
          <input
            type="text"
            value={form.rcloneRemote ?? 'gdrive'}
            onChange={(e) => setForm((f) => ({ ...f, rcloneRemote: e.target.value }))}
            placeholder="gdrive"
            className="input-field text-sm"
          />
          <p className="text-xs text-gray-600 mt-1">
            The rclone remote name (e.g., "gdrive" for Google Drive)
          </p>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1.5">Remote Path</label>
          <input
            type="text"
            value={form.rcloneRemotePath ?? 'Photos'}
            onChange={(e) => setForm((f) => ({ ...f, rcloneRemotePath: e.target.value }))}
            placeholder="Photos"
            className="input-field text-sm"
          />
          <p className="text-xs text-gray-600 mt-1">
            The path on the remote (e.g., "Photos/Library")
          </p>
        </div>

        <div>
          <button
            onClick={handleBackup}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Trigger Backup Now
          </button>
        </div>
      </div>

      {/* Import */}
      <div className="card space-y-4">
        <h3 className="text-white font-semibold">Import Settings</h3>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.autoImportEnabled ?? false}
            onChange={(e) => setForm((f) => ({ ...f, autoImportEnabled: e.target.checked }))}
            className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-blue-600"
          />
          <div>
            <div className="text-sm text-gray-300">Auto-import on SD card insert</div>
            <div className="text-xs text-gray-600">Automatically scan and import when an SD card is detected</div>
          </div>
        </label>
      </div>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={updateSettings.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {updateSettings.isPending ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Save Settings
            </>
          )}
        </button>
        {saved && (
          <span className="text-green-400 text-sm flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Settings saved
          </span>
        )}
      </div>
    </div>
  );
};

export default SettingsPanel;
