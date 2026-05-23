import { ipcMain, BrowserWindow } from 'electron';
import { getDatabase } from '../database/db';

interface DBTrip {
  id: number;
  name: string;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

function mapTrip(t: DBTrip, imageCount?: number, albumCount?: number) {
  return {
    id: t.id,
    name: t.name,
    startDate: t.start_date,
    endDate: t.end_date,
    description: t.description,
    imageCount: imageCount ?? 0,
    albumCount: albumCount ?? 0,
  };
}

export function registerTripHandlers(_win: BrowserWindow): void {
  // List trips
  ipcMain.handle('trips:list', () => {
    const db = getDatabase();
    const trips = db.prepare(`
      SELECT t.*,
        COUNT(DISTINCT aa.image_id) as image_count,
        COUNT(DISTINCT a.id) as album_count
      FROM trips t
      LEFT JOIN albums a ON a.trip_id = t.id
      LEFT JOIN album_assignments aa ON aa.album_id = a.id
      GROUP BY t.id
      ORDER BY t.start_date DESC NULLS LAST
    `).all() as (DBTrip & { image_count: number; album_count: number })[];

    return trips.map((t) => mapTrip(t, t.image_count, t.album_count));
  });

  // Create trip
  ipcMain.handle('trips:create', (_event, params: {
    name: string;
    startDate?: string;
    endDate?: string;
    description?: string;
  }) => {
    const db = getDatabase();
    const result = db.prepare(`
      INSERT INTO trips (name, start_date, end_date, description)
      VALUES (?, ?, ?, ?)
    `).run(params.name, params.startDate || null, params.endDate || null, params.description || null);

    const trip = db.prepare('SELECT * FROM trips WHERE id = ?').get(result.lastInsertRowid) as DBTrip;
    return mapTrip(trip, 0, 0);
  });

  // Update trip
  ipcMain.handle('trips:update', (_event, id: number, params: {
    name?: string;
    startDate?: string;
    endDate?: string;
    description?: string;
  }) => {
    const db = getDatabase();
    db.prepare(`
      UPDATE trips SET
        name = COALESCE(?, name),
        start_date = COALESCE(?, start_date),
        end_date = COALESCE(?, end_date),
        description = COALESCE(?, description)
      WHERE id = ?
    `).run(
      params.name ?? null,
      params.startDate ?? null,
      params.endDate ?? null,
      params.description ?? null,
      id
    );

    const trip = db.prepare('SELECT * FROM trips WHERE id = ?').get(id) as DBTrip;
    return mapTrip(trip);
  });

  // Delete trip
  ipcMain.handle('trips:delete', (_event, id: number) => {
    const db = getDatabase();
    // Unlink albums from trip
    db.prepare('UPDATE albums SET trip_id = NULL WHERE trip_id = ?').run(id);
    db.prepare('DELETE FROM trips WHERE id = ?').run(id);
    return { success: true };
  });

  // Get images for a trip
  ipcMain.handle('trips:get-images', (_event, tripId: number) => {
    const db = getDatabase();
    const images = db.prepare(`
      SELECT DISTINCT i.*,
        m.camera_model, m.iso, m.aperture, m.shutter_speed,
        m.focal_length, m.lens_info, m.date_taken, m.latitude, m.longitude
      FROM images i
      JOIN album_assignments aa ON aa.image_id = i.id
      JOIN albums a ON a.id = aa.album_id
      LEFT JOIN metadata m ON m.image_id = i.id
      WHERE a.trip_id = ?
      ORDER BY m.date_taken DESC NULLS LAST
    `).all(tripId) as (Record<string, unknown>)[];

    return images.map((img) => ({
      id: img.id,
      filename: img.filename,
      filepath: img.filepath,
      fileType: img.file_type,
      fileHash: img.file_hash,
      fileSize: img.file_size,
      createdAt: img.created_at,
      uploadedAt: img.uploaded_at,
      metadata: {
        cameraModel: img.camera_model,
        iso: img.iso,
        aperture: img.aperture,
        shutterSpeed: img.shutter_speed,
        focalLength: img.focal_length,
        lensInfo: img.lens_info,
        dateTaken: img.date_taken,
        latitude: img.latitude,
        longitude: img.longitude,
      },
      flags: [],
      albums: [],
    }));
  });
}
