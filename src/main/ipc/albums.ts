import { ipcMain, BrowserWindow } from 'electron';
import { getDatabase } from '../database/db';

interface DBAlbum {
  id: number;
  name: string;
  trip_id: number | null;
  created_at: string;
}

function mapAlbum(a: DBAlbum, imageCount?: number) {
  return {
    id: a.id,
    name: a.name,
    tripId: a.trip_id,
    createdAt: a.created_at,
    imageCount: imageCount ?? 0,
  };
}

export function registerAlbumHandlers(_win: BrowserWindow): void {
  // List albums
  ipcMain.handle('albums:list', () => {
    const db = getDatabase();
    const albums = db.prepare(`
      SELECT a.*, COUNT(aa.id) as image_count
      FROM albums a
      LEFT JOIN album_assignments aa ON aa.album_id = a.id
      GROUP BY a.id
      ORDER BY a.created_at DESC
    `).all() as (DBAlbum & { image_count: number })[];

    return albums.map((a) => mapAlbum(a, a.image_count));
  });

  // Create album
  ipcMain.handle('albums:create', (_event, params: { name: string; tripId?: number }) => {
    const db = getDatabase();
    const result = db.prepare(`
      INSERT INTO albums (name, trip_id) VALUES (?, ?)
    `).run(params.name, params.tripId || null);

    const album = db.prepare('SELECT * FROM albums WHERE id = ?').get(result.lastInsertRowid) as DBAlbum;
    return mapAlbum(album, 0);
  });

  // Assign/unassign images to album
  ipcMain.handle('albums:assign', (_event, params: {
    imageIds: number[];
    albumId: number;
    action: 'assign' | 'unassign';
  }) => {
    const db = getDatabase();
    const tx = db.transaction(() => {
      for (const imageId of params.imageIds) {
        if (params.action === 'assign') {
          db.prepare(`
            INSERT OR IGNORE INTO album_assignments (image_id, album_id)
            VALUES (?, ?)
          `).run(imageId, params.albumId);
        } else {
          db.prepare('DELETE FROM album_assignments WHERE image_id = ? AND album_id = ?')
            .run(imageId, params.albumId);
        }
      }
    });
    tx();
    return { success: true };
  });

  // Remove album
  ipcMain.handle('albums:remove', (_event, albumId: number) => {
    const db = getDatabase();
    db.prepare('DELETE FROM albums WHERE id = ?').run(albumId);
    return { success: true };
  });

  // Get images in album
  ipcMain.handle('albums:get-images', (_event, albumId: number) => {
    const db = getDatabase();
    const images = db.prepare(`
      SELECT i.*, m.camera_model, m.iso, m.aperture, m.shutter_speed,
             m.focal_length, m.lens_info, m.date_taken, m.latitude, m.longitude
      FROM images i
      JOIN album_assignments aa ON aa.image_id = i.id
      LEFT JOIN metadata m ON m.image_id = i.id
      WHERE aa.album_id = ?
      ORDER BY m.date_taken DESC NULLS LAST
    `).all(albumId) as (Record<string, unknown>)[];

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
