import { ipcMain, BrowserWindow, dialog } from 'electron';
import * as fs from 'fs';
import * as path from 'path';
import { getDatabase } from '../database/db';

export function registerExportHandlers(win: BrowserWindow): void {
  // Export to CSV
  ipcMain.handle('export:csv', async (_event, params: {
    albumId?: number;
    tripId?: number;
    startDate?: string;
    endDate?: string;
    fileType?: 'RAW' | 'JPG' | 'ALL';
    outputPath?: string;
  }) => {
    const db = getDatabase();

    const conditions: string[] = [];
    const bindings: (string | number)[] = [];

    if (params.fileType && params.fileType !== 'ALL') {
      conditions.push('i.file_type = ?');
      bindings.push(params.fileType);
    }

    if (params.albumId) {
      conditions.push('EXISTS (SELECT 1 FROM album_assignments aa WHERE aa.image_id = i.id AND aa.album_id = ?)');
      bindings.push(params.albumId);
    }

    if (params.tripId) {
      conditions.push(`EXISTS (
        SELECT 1 FROM album_assignments aa
        JOIN albums al ON al.id = aa.album_id
        WHERE aa.image_id = i.id AND al.trip_id = ?
      )`);
      bindings.push(params.tripId);
    }

    if (params.startDate) {
      conditions.push('m.date_taken >= ?');
      bindings.push(params.startDate);
    }

    if (params.endDate) {
      conditions.push('m.date_taken <= ?');
      bindings.push(params.endDate);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    const rows = db.prepare(`
      SELECT
        i.id, i.filename, i.filepath, i.file_type, i.file_hash, i.file_size,
        i.created_at, i.uploaded_at,
        m.camera_model, m.iso, m.aperture, m.shutter_speed,
        m.focal_length, m.lens_info, m.date_taken, m.latitude, m.longitude,
        m.city_cluster,
        GROUP_CONCAT(DISTINCT a.name) as albums,
        GROUP_CONCAT(DISTINCT f.flag_type) as flags
      FROM images i
      LEFT JOIN metadata m ON m.image_id = i.id
      LEFT JOIN album_assignments aa ON aa.image_id = i.id
      LEFT JOIN albums a ON a.id = aa.album_id
      LEFT JOIN flags f ON f.image_id = i.id
      ${whereClause}
      GROUP BY i.id
      ORDER BY m.date_taken DESC NULLS LAST
    `).all(bindings) as Record<string, unknown>[];

    // Choose output path
    let outputPath = params.outputPath;
    if (!outputPath) {
      const result = await dialog.showSaveDialog(win, {
        defaultPath: `photo-export-${new Date().toISOString().slice(0, 10)}.csv`,
        filters: [{ name: 'CSV', extensions: ['csv'] }],
      });
      if (result.canceled || !result.filePath) {
        return { success: false, rowsExported: 0, outputPath: '', error: 'Cancelled' };
      }
      outputPath = result.filePath;
    }

    // Generate CSV
    const headers = [
      'id', 'filename', 'filepath', 'file_type', 'file_hash', 'file_size',
      'created_at', 'uploaded_at',
      'camera_model', 'iso', 'aperture', 'shutter_speed',
      'focal_length', 'lens_info', 'date_taken', 'latitude', 'longitude',
      'city_cluster', 'albums', 'flags',
    ];

    const csvLines = [headers.join(',')];
    for (const row of rows) {
      const values = headers.map((h) => {
        const val = row[h];
        if (val === null || val === undefined) return '';
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      });
      csvLines.push(values.join(','));
    }

    const csvContent = csvLines.join('\n');
    fs.writeFileSync(path.resolve(outputPath), csvContent, 'utf-8');

    // Update sync state
    db.prepare(`
      UPDATE sync_state SET pending_exports = MAX(0, pending_exports - 1)
      WHERE id = 1
    `).run();

    return {
      success: true,
      rowsExported: rows.length,
      outputPath,
    };
  });
}
