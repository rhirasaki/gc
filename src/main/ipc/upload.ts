import { ipcMain, BrowserWindow } from 'electron';
import { getDatabase } from '../database/db';
import { uploadFile, pauseUpload, resumeUpload, cancelUpload } from '../services/rclone';

let uploadPaused = false;
let uploadInProgress = false;

export function registerUploadHandlers(win: BrowserWindow): void {
  // Start upload
  ipcMain.handle('upload:start', async (_event, params: {
    imageIds?: number[];
    albumId?: number;
    remote: string;
    remotePath: string;
    rclonePath?: string;
  }) => {
    const db = getDatabase();
    let imageIds: number[] = params.imageIds || [];

    // If albumId provided, get images from that album
    if (params.albumId) {
      const images = db.prepare(`
        SELECT i.id FROM images i
        JOIN album_assignments aa ON aa.image_id = i.id
        WHERE aa.album_id = ?
      `).all(params.albumId) as { id: number }[];
      imageIds = [...imageIds, ...images.map((i) => i.id)];
    }

    // If no specific images, get all unuploaded
    if (imageIds.length === 0) {
      const images = db.prepare(`
        SELECT i.id FROM images i
        WHERE i.uploaded_at IS NULL
      `).all() as { id: number }[];
      imageIds = images.map((i) => i.id);
    }

    // Filter out flagged DO_NOT_UPLOAD
    const filteredIds = imageIds.filter((id) => {
      const flag = db.prepare(`
        SELECT id FROM flags WHERE image_id = ? AND flag_type = 'DO_NOT_UPLOAD'
      `).get(id);
      return !flag;
    });

    if (filteredIds.length === 0) {
      return { success: true, queued: 0 };
    }

    // Queue images for upload
    const tx = db.transaction(() => {
      for (const imageId of filteredIds) {
        db.prepare(`
          INSERT OR IGNORE INTO upload_log (image_id, status, attempt_count)
          VALUES (?, 'QUEUED', 0)
        `).run(imageId);
      }
    });
    tx();

    // Start upload process in background
    uploadInProgress = true;
    uploadPaused = false;

    void runUploadQueue(win, params.remote, params.remotePath, params.rclonePath);

    return { success: true, queued: filteredIds.length };
  });

  // Pause upload
  ipcMain.handle('upload:pause', () => {
    uploadPaused = true;
    pauseUpload();
  });

  // Resume upload
  ipcMain.handle('upload:resume', () => {
    uploadPaused = false;
    resumeUpload();
  });

  // Cancel upload
  ipcMain.handle('upload:cancel', () => {
    uploadInProgress = false;
    cancelUpload();
  });

  // Get upload status
  ipcMain.handle('upload:status', () => {
    const db = getDatabase();

    const queued = (db.prepare("SELECT COUNT(*) as count FROM upload_log WHERE status = 'QUEUED'").get() as { count: number }).count;
    const uploaded = (db.prepare("SELECT COUNT(*) as count FROM upload_log WHERE status = 'UPLOADED'").get() as { count: number }).count;
    const failed = (db.prepare("SELECT COUNT(*) as count FROM upload_log WHERE status = 'FAILED'").get() as { count: number }).count;

    return {
      queued,
      uploaded,
      failed,
      inProgress: uploadInProgress,
    };
  });
}

async function runUploadQueue(
  win: BrowserWindow,
  remote: string,
  remotePath: string,
  rclonePath?: string
): Promise<void> {
  const db = getDatabase();

  while (uploadInProgress) {
    if (uploadPaused) {
      await sleep(1000);
      continue;
    }

    const item = db.prepare(`
      SELECT ul.id, ul.image_id, i.filepath, i.filename
      FROM upload_log ul
      JOIN images i ON i.id = ul.image_id
      WHERE ul.status = 'QUEUED'
      ORDER BY ul.id ASC
      LIMIT 1
    `).get() as { id: number; image_id: number; filepath: string; filename: string } | null;

    if (!item) {
      uploadInProgress = false;
      break;
    }

    win.webContents.send('upload:progress', {
      imageId: item.image_id,
      filename: item.filename,
      percentage: 0,
      status: 'uploading',
    });

    try {
      await uploadFile(
        item.filepath,
        { remote, remotePath, localPath: item.filepath, rclonePath },
        (progress) => {
          win.webContents.send('upload:progress', {
            imageId: item.image_id,
            filename: item.filename,
            percentage: progress.percentage,
            status: 'uploading',
          });
        }
      );

      db.prepare(`
        UPDATE upload_log SET status = 'UPLOADED', uploaded_at = datetime('now'),
        attempt_count = attempt_count + 1
        WHERE id = ?
      `).run(item.id);

      db.prepare(`
        UPDATE images SET uploaded_at = datetime('now') WHERE id = ?
      `).run(item.image_id);

      win.webContents.send('upload:progress', {
        imageId: item.image_id,
        filename: item.filename,
        percentage: 100,
        status: 'done',
      });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      db.prepare(`
        UPDATE upload_log SET status = 'FAILED', error_message = ?,
        attempt_count = attempt_count + 1
        WHERE id = ?
      `).run(errorMsg, item.id);

      win.webContents.send('upload:progress', {
        imageId: item.image_id,
        filename: item.filename,
        percentage: 0,
        status: 'failed',
        error: errorMsg,
      });
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
