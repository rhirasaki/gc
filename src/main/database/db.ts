import Database from 'better-sqlite3';
import path from 'path';
import { app } from 'electron';
import { initializeSchema } from './schema';

let dbInstance: Database.Database | null = null;

export function getDatabase(): Database.Database {
  if (!dbInstance) {
    const userDataPath = app.getPath('userData');
    const dbPath = path.join(userDataPath, 'photo-organizer.db');
    dbInstance = new Database(dbPath);
    dbInstance.pragma('journal_mode = WAL');
    dbInstance.pragma('foreign_keys = ON');
    initializeSchema(dbInstance);
  }
  return dbInstance;
}

export function closeDatabase(): void {
  if (dbInstance) {
    dbInstance.close();
    dbInstance = null;
  }
}
