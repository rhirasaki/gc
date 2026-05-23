import { ipcMain, BrowserWindow } from 'electron';
import { getDatabase } from '../database/db';

interface DBImage {
  id: number;
  filename: string;
  filepath: string;
  file_type: string;
  file_hash: string | null;
  file_size: number | null;
  created_at: string;
  uploaded_at: string | null;
}

interface DBMetadata {
  id: number;
  image_id: number;
  camera_model: string | null;
  iso: number | null;
  aperture: number | null;
  shutter_speed: string | null;
  focal_length: number | null;
  lens_info: string | null;
  date_taken: string | null;
  latitude: number | null;
  longitude: number | null;
  city_cluster: string | null;
}

interface DBFlag {
  id: number;
  image_id: number;
  flag_type: string;
  set_at: string;
  reason: string | null;
}

interface DBAlbum {
  id: number;
  name: string;
  trip_id: number | null;
  created_at: string;
}

function mapImage(img: DBImage, metadata: DBMetadata | null, flags: DBFlag[], albums: DBAlbum[]) {
  return {
    id: img.id,
    filename: img.filename,
    filepath: img.filepath,
    fileType: img.file_type,
    fileHash: img.file_hash,
    fileSize: img.file_size,
    createdAt: img.created_at,
    uploadedAt: img.uploaded_at,
    metadata: metadata ? {
      id: metadata.id,
      imageId: metadata.image_id,
      cameraModel: metadata.camera_model,
      iso: metadata.iso,
      aperture: metadata.aperture,
      shutterSpeed: metadata.shutter_speed,
      focalLength: metadata.focal_length,
      lensInfo: metadata.lens_info,
      dateTaken: metadata.date_taken,
      latitude: metadata.latitude,
      longitude: metadata.longitude,
      cityCluster: metadata.city_cluster,
    } : {},
    flags: flags.map((f) => ({
      id: f.id,
      imageId: f.image_id,
      flagType: f.flag_type,
      setAt: f.set_at,
      reason: f.reason,
    })),
    albums: albums.map((a) => ({
      id: a.id,
      name: a.name,
      tripId: a.trip_id,
      createdAt: a.created_at,
    })),
  };
}

export function registerImageHandlers(_win: BrowserWindow): void {
  // List images with filters and pagination
  ipcMain.handle('images:list', (_event, params: {
    page?: number;
    pageSize?: number;
    fileType?: 'RAW' | 'JPG' | 'ALL';
    albumId?: number;
    tripId?: number;
    startDate?: string;
    endDate?: string;
    flagged?: boolean;
    search?: string;
    sortBy?: string;
    sortOrder?: string;
  }) => {
    const db = getDatabase();
    const page = params.page || 1;
    const pageSize = params.pageSize || 50;
    const offset = (page - 1) * pageSize;
    const sortBy = params.sortBy || 'date_taken';
    const sortOrder = params.sortOrder || 'DESC';

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

    if (params.flagged) {
      conditions.push('EXISTS (SELECT 1 FROM flags f WHERE f.image_id = i.id)');
    }

    if (params.search) {
      conditions.push('(i.filename LIKE ? OR m.camera_model LIKE ?)');
      bindings.push(`%${params.search}%`, `%${params.search}%`);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    const validSortColumns: Record<string, string> = {
      date_taken: 'm.date_taken',
      filename: 'i.filename',
      file_size: 'i.file_size',
      created_at: 'i.created_at',
    };
    const sortCol = validSortColumns[sortBy] || 'm.date_taken';
    const sortDir = sortOrder === 'ASC' ? 'ASC' : 'DESC';

    const query = `
      SELECT i.*
      FROM images i
      LEFT JOIN metadata m ON m.image_id = i.id
      ${whereClause}
      ORDER BY ${sortCol} ${sortDir} NULLS LAST
      LIMIT ? OFFSET ?
    `;

    const countQuery = `
      SELECT COUNT(*) as total
      FROM images i
      LEFT JOIN metadata m ON m.image_id = i.id
      ${whereClause}
    `;

    const images = db.prepare(query).all([...bindings, pageSize, offset]) as DBImage[];
    const countResult = db.prepare(countQuery).get(bindings) as { total: number };

    const result = images.map((img) => {
      const metadata = db.prepare('SELECT * FROM metadata WHERE image_id = ?').get(img.id) as DBMetadata | null;
      const flags = db.prepare('SELECT * FROM flags WHERE image_id = ?').all(img.id) as DBFlag[];
      const albums = db.prepare(`
        SELECT a.* FROM albums a
        JOIN album_assignments aa ON aa.album_id = a.id
        WHERE aa.image_id = ?
      `).all(img.id) as DBAlbum[];
      return mapImage(img, metadata, flags, albums);
    });

    return {
      images: result,
      total: countResult.total,
      page,
      pageSize,
    };
  });

  // Get single image
  ipcMain.handle('images:get', (_event, id: number) => {
    const db = getDatabase();
    const img = db.prepare('SELECT * FROM images WHERE id = ?').get(id) as DBImage | null;
    if (!img) return null;
    const metadata = db.prepare('SELECT * FROM metadata WHERE image_id = ?').get(id) as DBMetadata | null;
    const flags = db.prepare('SELECT * FROM flags WHERE image_id = ?').all(id) as DBFlag[];
    const albums = db.prepare(`
      SELECT a.* FROM albums a
      JOIN album_assignments aa ON aa.album_id = a.id
      WHERE aa.image_id = ?
    `).all(id) as DBAlbum[];
    return mapImage(img, metadata, flags, albums);
  });

  // Flag images
  ipcMain.handle('images:flag', (_event, params: {
    imageIds: number[];
    flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW';
    action: 'set' | 'unset';
    reason?: string;
  }) => {
    const db = getDatabase();
    let updated = 0;

    const tx = db.transaction(() => {
      for (const imageId of params.imageIds) {
        if (params.action === 'set') {
          db.prepare(`
            INSERT OR REPLACE INTO flags (image_id, flag_type, reason)
            VALUES (?, ?, ?)
          `).run(imageId, params.flagType, params.reason || null);
        } else {
          db.prepare('DELETE FROM flags WHERE image_id = ? AND flag_type = ?')
            .run(imageId, params.flagType);
        }
        updated++;
      }
    });

    tx();
    return { success: true, updated };
  });

  // Delete images
  ipcMain.handle('images:delete', (_event, ids: number[]) => {
    const db = getDatabase();
    const tx = db.transaction(() => {
      for (const id of ids) {
        db.prepare('DELETE FROM images WHERE id = ?').run(id);
      }
    });
    tx();
    return { success: true, deleted: ids.map(String), errors: [] };
  });

  // Update metadata
  ipcMain.handle('images:update-metadata', (_event, id: number, metadata: {
    cameraModel?: string;
    iso?: number;
    aperture?: number;
    shutterSpeed?: string;
    focalLength?: number;
    lensInfo?: string;
    dateTaken?: string;
    latitude?: number;
    longitude?: number;
    cityCluster?: string;
  }) => {
    const db = getDatabase();
    const existing = db.prepare('SELECT id FROM metadata WHERE image_id = ?').get(id);
    if (existing) {
      db.prepare(`
        UPDATE metadata SET
          camera_model = COALESCE(?, camera_model),
          iso = COALESCE(?, iso),
          aperture = COALESCE(?, aperture),
          shutter_speed = COALESCE(?, shutter_speed),
          focal_length = COALESCE(?, focal_length),
          lens_info = COALESCE(?, lens_info),
          date_taken = COALESCE(?, date_taken),
          latitude = COALESCE(?, latitude),
          longitude = COALESCE(?, longitude),
          city_cluster = COALESCE(?, city_cluster)
        WHERE image_id = ?
      `).run(
        metadata.cameraModel ?? null,
        metadata.iso ?? null,
        metadata.aperture ?? null,
        metadata.shutterSpeed ?? null,
        metadata.focalLength ?? null,
        metadata.lensInfo ?? null,
        metadata.dateTaken ?? null,
        metadata.latitude ?? null,
        metadata.longitude ?? null,
        metadata.cityCluster ?? null,
        id
      );
    }
  });

  // Get analytics data
  ipcMain.handle('images:analytics', () => {
    const db = getDatabase();

    const totalImages = (db.prepare('SELECT COUNT(*) as count FROM images').get() as { count: number }).count;
    const rawCount = (db.prepare("SELECT COUNT(*) as count FROM images WHERE file_type = 'RAW'").get() as { count: number }).count;
    const jpgCount = (db.prepare("SELECT COUNT(*) as count FROM images WHERE file_type = 'JPG'").get() as { count: number }).count;
    const uploadedCount = (db.prepare('SELECT COUNT(*) as count FROM images WHERE uploaded_at IS NOT NULL').get() as { count: number }).count;

    const byCamera = db.prepare(`
      SELECT camera_model, COUNT(*) as count
      FROM metadata
      WHERE camera_model IS NOT NULL
      GROUP BY camera_model
      ORDER BY count DESC
      LIMIT 10
    `).all() as { camera_model: string; count: number }[];

    const byDate = db.prepare(`
      SELECT strftime('%Y-%m', date_taken) as month, COUNT(*) as count
      FROM metadata
      WHERE date_taken IS NOT NULL
      GROUP BY month
      ORDER BY month DESC
      LIMIT 12
    `).all() as { month: string; count: number }[];

    const withLocation = (db.prepare(`
      SELECT COUNT(*) as count FROM metadata
      WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    `).get() as { count: number }).count;

    return {
      totalImages,
      rawCount,
      jpgCount,
      uploadedCount,
      withLocation,
      byCamera,
      byDate,
    };
  });
}
