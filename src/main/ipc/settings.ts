import { ipcMain, BrowserWindow, dialog } from 'electron';
import { getDatabase } from '../database/db';

// Ensure app_settings table exists
function ensureSettingsTable(): void {
  const db = getDatabase();
  db.exec(`
    CREATE TABLE IF NOT EXISTS app_settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('libraryPath', '');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('rcloneRemote', 'gdrive');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('rcloneRemotePath', 'Photos');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('rclonePath', 'rclone');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('autoImportEnabled', 'false');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('thumbnailSize', '200');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('theme', 'dark');
  `);
}

export function registerSettingsHandlers(win: BrowserWindow): void {
  ensureSettingsTable();

  // Get settings
  ipcMain.handle('settings:get', () => {
    ensureSettingsTable();
    const db = getDatabase();
    const rows = db.prepare('SELECT key, value FROM app_settings').all() as { key: string; value: string }[];
    const settings: Record<string, string | boolean | number> = {};
    for (const row of rows) {
      if (row.value === 'true' || row.value === 'false') {
        settings[row.key] = row.value === 'true';
      } else if (!isNaN(Number(row.value)) && row.value !== '') {
        settings[row.key] = Number(row.value);
      } else {
        settings[row.key] = row.value;
      }
    }
    return settings;
  });

  // Set settings
  ipcMain.handle('settings:set', (_event, settings: Record<string, string | boolean | number>) => {
    ensureSettingsTable();
    const db = getDatabase();
    const tx = db.transaction(() => {
      for (const [key, value] of Object.entries(settings)) {
        db.prepare('INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)')
          .run(key, String(value));
      }
    });
    tx();
    return { success: true };
  });

  // File system helpers
  ipcMain.handle('fs:select-directory', async () => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openDirectory'],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
  });

  ipcMain.handle('fs:select-file', async (_event, filters?: { name: string; extensions: string[] }[]) => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openFile'],
      filters: filters || [],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
  });

  // Thumbnail generation (return the image path - in production would generate actual thumbnails)
  ipcMain.handle('fs:get-thumbnail', (_event, imagePath: string) => {
    // Return the original path - Electron can serve local files
    return `file://${imagePath}`;
  });
}
