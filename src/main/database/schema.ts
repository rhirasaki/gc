import Database from 'better-sqlite3';

export function initializeSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS trips (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      start_date TEXT,
      end_date TEXT,
      description TEXT
    );

    CREATE TABLE IF NOT EXISTS images (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      filename TEXT NOT NULL,
      filepath TEXT NOT NULL UNIQUE,
      file_type TEXT NOT NULL CHECK(file_type IN ('RAW','JPG')),
      file_hash TEXT,
      file_size INTEGER,
      created_at TEXT DEFAULT (datetime('now')),
      uploaded_at TEXT
    );

    CREATE TABLE IF NOT EXISTS metadata (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
      camera_model TEXT,
      iso INTEGER,
      aperture REAL,
      shutter_speed TEXT,
      focal_length REAL,
      lens_info TEXT,
      date_taken TEXT,
      latitude REAL,
      longitude REAL,
      city_cluster TEXT
    );

    CREATE TABLE IF NOT EXISTS relationships (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      image_id_1 INTEGER NOT NULL REFERENCES images(id),
      image_id_2 INTEGER NOT NULL REFERENCES images(id),
      relationship_type TEXT NOT NULL DEFAULT 'RAW_JPG_PAIR',
      flags TEXT
    );

    CREATE TABLE IF NOT EXISTS albums (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      trip_id INTEGER REFERENCES trips(id),
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS album_assignments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      image_id INTEGER NOT NULL REFERENCES images(id),
      album_id INTEGER NOT NULL REFERENCES albums(id),
      batch_assigned_at TEXT DEFAULT (datetime('now')),
      UNIQUE(image_id, album_id)
    );

    CREATE TABLE IF NOT EXISTS flags (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      image_id INTEGER NOT NULL REFERENCES images(id),
      flag_type TEXT NOT NULL CHECK(flag_type IN ('DO_NOT_UPLOAD','FLAGGED_FOR_REVIEW')),
      set_at TEXT DEFAULT (datetime('now')),
      reason TEXT,
      UNIQUE(image_id, flag_type)
    );

    CREATE TABLE IF NOT EXISTS upload_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      image_id INTEGER NOT NULL REFERENCES images(id),
      album_id INTEGER REFERENCES albums(id),
      status TEXT NOT NULL DEFAULT 'QUEUED' CHECK(status IN ('QUEUED','UPLOADED','FAILED','SKIPPED')),
      attempt_count INTEGER DEFAULT 0,
      error_message TEXT,
      uploaded_at TEXT
    );

    CREATE TABLE IF NOT EXISTS sync_state (
      id INTEGER PRIMARY KEY DEFAULT 1,
      last_backup_to_gdrive TEXT,
      last_rclone_sync TEXT,
      pending_exports INTEGER DEFAULT 0
    );

    INSERT OR IGNORE INTO sync_state (id) VALUES (1);

    CREATE INDEX IF NOT EXISTS idx_images_hash ON images(file_hash);
    CREATE INDEX IF NOT EXISTS idx_images_type ON images(file_type);
    CREATE INDEX IF NOT EXISTS idx_metadata_image_id ON metadata(image_id);
    CREATE INDEX IF NOT EXISTS idx_metadata_date_taken ON metadata(date_taken);
    CREATE INDEX IF NOT EXISTS idx_metadata_location ON metadata(latitude, longitude);
    CREATE INDEX IF NOT EXISTS idx_upload_log_status ON upload_log(status);
    CREATE INDEX IF NOT EXISTS idx_upload_log_image_id ON upload_log(image_id);
    CREATE INDEX IF NOT EXISTS idx_album_assignments_image ON album_assignments(image_id);
    CREATE INDEX IF NOT EXISTS idx_album_assignments_album ON album_assignments(album_id);
    CREATE INDEX IF NOT EXISTS idx_flags_image_id ON flags(image_id);

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
