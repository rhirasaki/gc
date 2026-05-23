import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import { getDatabase, closeDatabase } from './database/db';
import { registerImportHandlers } from './ipc/import';
import { registerImageHandlers } from './ipc/images';
import { registerAlbumHandlers } from './ipc/albums';
import { registerUploadHandlers } from './ipc/upload';
import { registerExportHandlers } from './ipc/export';
import { registerSettingsHandlers } from './ipc/settings';
import { registerTripHandlers } from './ipc/trips';

let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0a0a0f',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
    },
  });

  // Load app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  // Initialize database
  getDatabase();

  createWindow();

  // Register all IPC handlers
  if (mainWindow) {
    registerImportHandlers(mainWindow);
    registerImageHandlers(mainWindow);
    registerAlbumHandlers(mainWindow);
    registerUploadHandlers(mainWindow);
    registerExportHandlers(mainWindow);
    registerSettingsHandlers(mainWindow);
    registerTripHandlers(mainWindow);
  }

  // Register backup IPC handler
  ipcMain.handle('backup:trigger', async () => {
    const { triggerGoogleDriveBackup } = await import('./services/backup');
    const settings = await getSettings();
    return triggerGoogleDriveBackup({
      remote: settings.rcloneRemote || 'gdrive',
      remotePath: settings.rcloneRemotePath || 'Photos',
      rclonePath: settings.rclonePath,
    });
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  closeDatabase();
});

async function getSettings(): Promise<Record<string, string>> {
  const db = getDatabase();
  const rows = db.prepare('SELECT key, value FROM app_settings').all() as { key: string; value: string }[];
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}
