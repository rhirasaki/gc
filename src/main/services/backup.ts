import { getDatabase } from '../database/db';
import { uploadFile } from './rclone';

export interface BackupOptions {
  remote: string;
  remotePath: string;
  rclonePath?: string;
  onProgress?: (imageId: number, percentage: number) => void;
}

export async function triggerGoogleDriveBackup(options: BackupOptions): Promise<{
  success: number;
  failed: number;
  errors: string[];
}> {
  const db = getDatabase();
  const errors: string[] = [];
  let success = 0;
  let failed = 0;

  // Get all images not yet uploaded
  const images = db.prepare(`
    SELECT i.id, i.filepath, i.filename
    FROM images i
    LEFT JOIN upload_log ul ON ul.image_id = i.id AND ul.status = 'UPLOADED'
    WHERE ul.id IS NULL AND i.uploaded_at IS NULL
  `).all() as { id: number; filepath: string; filename: string }[];

  for (const image of images) {
    // Insert into upload_log as QUEUED
    const logEntry = db.prepare(`
      INSERT OR IGNORE INTO upload_log (image_id, status, attempt_count)
      VALUES (?, 'QUEUED', 0)
    `).run(image.id);

    const logId = logEntry.lastInsertRowid as number;

    try {
      await uploadFile(
        image.filepath,
        {
          remote: options.remote,
          remotePath: options.remotePath,
          localPath: image.filepath,
          rclonePath: options.rclonePath,
        },
        (progress) => {
          options.onProgress?.(image.id, progress.percentage);
        }
      );

      // Mark as uploaded
      db.prepare(`
        UPDATE upload_log SET status = 'UPLOADED', uploaded_at = datetime('now'),
        attempt_count = attempt_count + 1
        WHERE id = ?
      `).run(logId);

      db.prepare(`
        UPDATE images SET uploaded_at = datetime('now') WHERE id = ?
      `).run(image.id);

      success++;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      errors.push(`${image.filename}: ${errorMsg}`);

      db.prepare(`
        UPDATE upload_log SET status = 'FAILED', error_message = ?,
        attempt_count = attempt_count + 1
        WHERE id = ?
      `).run(errorMsg, logId);

      failed++;
    }
  }

  // Update sync state
  db.prepare(`
    UPDATE sync_state SET last_backup_to_gdrive = datetime('now') WHERE id = 1
  `).run();

  return { success, failed, errors };
}
