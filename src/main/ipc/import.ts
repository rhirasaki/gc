import { ipcMain, BrowserWindow } from 'electron';
import * as fs from 'fs';
import * as path from 'path';
import { getDatabase } from '../database/db';
import { scanDirectory, detectPairs, ScannedFile } from '../services/scanner';

export function registerImportHandlers(win: BrowserWindow): void {
  // Scan a directory
  ipcMain.handle('import:scan', async (_event, directory: string) => {
    try {
      const files = await scanDirectory(directory, (progress) => {
        win.webContents.send('import:scan-progress', progress);
      });

      const pairs = detectPairs(files);
      const pairList = Array.from(pairs.entries()).map(([baseName, pair]) => ({
        baseName,
        raw: pair.raw || null,
        jpg: pair.jpg || null,
      }));

      return { success: true, files, pairs: pairList, total: files.length };
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      return { success: false, error: errorMsg };
    }
  });

  // Confirm import - copy files to library
  ipcMain.handle('import:confirm', async (_event, params: {
    files: ScannedFile[];
    destinationDir: string;
  }) => {
    const db = getDatabase();
    const { files, destinationDir } = params;
    let processed = 0;
    const errors: string[] = [];

    try {
      fs.mkdirSync(destinationDir, { recursive: true });
    } catch {
      // Directory may already exist
    }

    for (const file of files) {
      try {
        const destPath = path.join(destinationDir, file.filename);
        let finalDestPath = destPath;

        // Handle filename conflicts
        if (fs.existsSync(destPath)) {
          const ext = path.extname(file.filename);
          const base = path.basename(file.filename, ext);
          finalDestPath = path.join(destinationDir, `${base}_${Date.now()}${ext}`);
        }

        fs.copyFileSync(file.filepath, finalDestPath);

        // Insert into database
        const existing = db.prepare('SELECT id FROM images WHERE file_hash = ?').get(file.fileHash);
        if (!existing) {
          const result = db.prepare(`
            INSERT OR IGNORE INTO images (filename, filepath, file_type, file_hash, file_size)
            VALUES (?, ?, ?, ?, ?)
          `).run(
            path.basename(finalDestPath),
            finalDestPath,
            file.fileType,
            file.fileHash,
            file.fileSize
          );

          if (result.lastInsertRowid) {
            const imageId = result.lastInsertRowid as number;
            db.prepare(`
              INSERT INTO metadata (
                image_id, camera_model, iso, aperture, shutter_speed,
                focal_length, lens_info, date_taken, latitude, longitude
              ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            `).run(
              imageId,
              file.metadata.cameraModel || null,
              file.metadata.iso || null,
              file.metadata.aperture || null,
              file.metadata.shutterSpeed || null,
              file.metadata.focalLength || null,
              file.metadata.lensInfo || null,
              file.metadata.dateTaken || null,
              file.metadata.latitude || null,
              file.metadata.longitude || null
            );
          }
        }

        processed++;
        win.webContents.send('import:confirm-progress', {
          total: files.length,
          processed,
          currentFile: file.filename,
        });
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        errors.push(`${file.filename}: ${errorMsg}`);
      }
    }

    return { success: true, processed, errors };
  });

  // Delete files from SD card after import
  ipcMain.handle('import:delete-from-sd', async (_event, filepaths: string[]) => {
    const deleted: string[] = [];
    const errors: string[] = [];

    for (const filepath of filepaths) {
      try {
        fs.unlinkSync(filepath);
        deleted.push(filepath);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        errors.push(`${filepath}: ${errorMsg}`);
      }
    }

    return { success: true, deleted, errors };
  });
}
