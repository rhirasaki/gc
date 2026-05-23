import { contextBridge, ipcRenderer } from 'electron';

// Types for the API
export interface ElectronAPI {
  // Import
  importScan: (directory: string) => Promise<ScanResult>;
  importConfirm: (params: ImportConfirmParams) => Promise<ImportResult>;
  importDeleteFromSD: (filepaths: string[]) => Promise<DeleteResult>;
  onImportScanProgress: (callback: (progress: ScanProgress) => void) => () => void;
  onImportConfirmProgress: (callback: (progress: ConfirmProgress) => void) => () => void;

  // Images
  imagesList: (params: ImagesListParams) => Promise<ImagesListResult>;
  imagesGet: (id: number) => Promise<ImageWithMetadata | null>;
  imagesFlag: (params: ImageFlagParams) => Promise<FlagResult>;
  imagesDelete: (ids: number[]) => Promise<DeleteResult>;
  imagesUpdateMetadata: (id: number, metadata: Partial<ImageMetadata>) => Promise<void>;

  // Albums
  albumsList: () => Promise<Album[]>;
  albumsCreate: (params: { name: string; tripId?: number }) => Promise<Album>;
  albumsAssign: (params: AlbumAssignParams) => Promise<void>;
  albumsRemove: (albumId: number) => Promise<void>;
  albumsGetImages: (albumId: number) => Promise<ImageWithMetadata[]>;

  // Trips
  tripsList: () => Promise<Trip[]>;
  tripsCreate: (params: TripCreateParams) => Promise<Trip>;
  tripsUpdate: (id: number, params: Partial<TripCreateParams>) => Promise<Trip>;
  tripsDelete: (id: number) => Promise<void>;
  tripsGetImages: (tripId: number) => Promise<ImageWithMetadata[]>;

  // Upload
  uploadStart: (params: UploadStartParams) => Promise<UploadStartResult>;
  uploadPause: () => Promise<void>;
  uploadResume: () => Promise<void>;
  uploadStatus: () => Promise<UploadStatus>;
  onUploadProgress: (callback: (progress: UploadProgressEvent) => void) => () => void;

  // Export
  exportCsv: (params: ExportCsvParams) => Promise<ExportResult>;

  // Settings
  settingsGet: () => Promise<AppSettings>;
  settingsSet: (settings: Partial<AppSettings>) => Promise<void>;

  // Backup
  backupTrigger: () => Promise<BackupResult>;

  // Analytics
  imagesAnalytics: () => Promise<AnalyticsData>;

  // File system
  selectDirectory: () => Promise<string | null>;
  selectFile: (filters?: FileFilter[]) => Promise<string | null>;
  getThumbnailPath: (imagePath: string) => Promise<string>;
}

export interface AnalyticsData {
  totalImages: number;
  rawCount: number;
  jpgCount: number;
  uploadedCount: number;
  withLocation: number;
  byCamera: { camera_model: string; count: number }[];
  byDate: { month: string; count: number }[];
}

// Type definitions
export interface ScanResult {
  success: boolean;
  files?: ScannedFile[];
  pairs?: PairInfo[];
  total?: number;
  error?: string;
}

export interface ScannedFile {
  filename: string;
  filepath: string;
  fileType: 'RAW' | 'JPG';
  fileSize: number;
  fileHash: string;
  metadata: {
    cameraMake?: string;
    cameraModel?: string;
    iso?: number;
    aperture?: number;
    shutterSpeed?: string;
    focalLength?: number;
    lensInfo?: string;
    dateTaken?: string;
    latitude?: number;
    longitude?: number;
  };
}

export interface PairInfo {
  baseName: string;
  raw: ScannedFile | null;
  jpg: ScannedFile | null;
}

export interface ImportConfirmParams {
  files: ScannedFile[];
  destinationDir: string;
}

export interface ImportResult {
  success: boolean;
  processed: number;
  errors: string[];
}

export interface DeleteResult {
  success: boolean;
  deleted: string[];
  errors: string[];
}

export interface ScanProgress {
  total: number;
  processed: number;
  currentFile: string;
}

export interface ConfirmProgress {
  total: number;
  processed: number;
  currentFile: string;
}

export interface ImagesListParams {
  page?: number;
  pageSize?: number;
  fileType?: 'RAW' | 'JPG' | 'ALL';
  albumId?: number;
  tripId?: number;
  startDate?: string;
  endDate?: string;
  flagged?: boolean;
  search?: string;
  sortBy?: 'date_taken' | 'filename' | 'file_size' | 'created_at';
  sortOrder?: 'ASC' | 'DESC';
}

export interface ImageWithMetadata {
  id: number;
  filename: string;
  filepath: string;
  fileType: 'RAW' | 'JPG';
  fileHash: string | null;
  fileSize: number | null;
  createdAt: string;
  uploadedAt: string | null;
  metadata: ImageMetadata;
  flags: ImageFlag[];
  albums: Album[];
}

export interface ImageMetadata {
  id?: number;
  imageId?: number;
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
}

export interface ImageFlag {
  id: number;
  imageId: number;
  flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW';
  setAt: string;
  reason?: string;
}

export interface ImagesListResult {
  images: ImageWithMetadata[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ImageFlagParams {
  imageIds: number[];
  flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW';
  action: 'set' | 'unset';
  reason?: string;
}

export interface FlagResult {
  success: boolean;
  updated: number;
}

export interface Album {
  id: number;
  name: string;
  tripId: number | null;
  createdAt: string;
  imageCount?: number;
}

export interface AlbumAssignParams {
  imageIds: number[];
  albumId: number;
  action: 'assign' | 'unassign';
}

export interface Trip {
  id: number;
  name: string;
  startDate: string | null;
  endDate: string | null;
  description: string | null;
  imageCount?: number;
  albumCount?: number;
}

export interface TripCreateParams {
  name: string;
  startDate?: string;
  endDate?: string;
  description?: string;
}

export interface UploadStartParams {
  imageIds?: number[];
  albumId?: number;
  remote: string;
  remotePath: string;
  rclonePath?: string;
}

export interface UploadStartResult {
  success: boolean;
  queued: number;
  error?: string;
}

export interface UploadStatus {
  queued: number;
  uploaded: number;
  failed: number;
  inProgress: boolean;
  currentFile?: string;
}

export interface UploadProgressEvent {
  imageId: number;
  filename: string;
  percentage: number;
  status: 'uploading' | 'done' | 'failed';
  error?: string;
}

export interface ExportCsvParams {
  albumId?: number;
  tripId?: number;
  startDate?: string;
  endDate?: string;
  fileType?: 'RAW' | 'JPG' | 'ALL';
  outputPath: string;
}

export interface ExportResult {
  success: boolean;
  rowsExported: number;
  outputPath: string;
  error?: string;
}

export interface AppSettings {
  libraryPath: string;
  rcloneRemote: string;
  rcloneRemotePath: string;
  rclonePath: string;
  autoImportEnabled: boolean;
  thumbnailSize: number;
  theme: 'dark' | 'light';
}

export interface BackupResult {
  success: number;
  failed: number;
  errors: string[];
}

export interface FileFilter {
  name: string;
  extensions: string[];
}

// Expose API via contextBridge
const api: ElectronAPI = {
  // Import
  importScan: (directory) => ipcRenderer.invoke('import:scan', directory),
  importConfirm: (params) => ipcRenderer.invoke('import:confirm', params),
  importDeleteFromSD: (filepaths) => ipcRenderer.invoke('import:delete-from-sd', filepaths),
  onImportScanProgress: (callback) => {
    const listener = (_: Electron.IpcRendererEvent, progress: ScanProgress) => callback(progress);
    ipcRenderer.on('import:scan-progress', listener);
    return () => ipcRenderer.removeListener('import:scan-progress', listener);
  },
  onImportConfirmProgress: (callback) => {
    const listener = (_: Electron.IpcRendererEvent, progress: ConfirmProgress) => callback(progress);
    ipcRenderer.on('import:confirm-progress', listener);
    return () => ipcRenderer.removeListener('import:confirm-progress', listener);
  },

  // Images
  imagesList: (params) => ipcRenderer.invoke('images:list', params),
  imagesGet: (id) => ipcRenderer.invoke('images:get', id),
  imagesFlag: (params) => ipcRenderer.invoke('images:flag', params),
  imagesDelete: (ids) => ipcRenderer.invoke('images:delete', ids),
  imagesUpdateMetadata: (id, metadata) => ipcRenderer.invoke('images:update-metadata', id, metadata),

  // Albums
  albumsList: () => ipcRenderer.invoke('albums:list'),
  albumsCreate: (params) => ipcRenderer.invoke('albums:create', params),
  albumsAssign: (params) => ipcRenderer.invoke('albums:assign', params),
  albumsRemove: (albumId) => ipcRenderer.invoke('albums:remove', albumId),
  albumsGetImages: (albumId) => ipcRenderer.invoke('albums:get-images', albumId),

  // Trips
  tripsList: () => ipcRenderer.invoke('trips:list'),
  tripsCreate: (params) => ipcRenderer.invoke('trips:create', params),
  tripsUpdate: (id, params) => ipcRenderer.invoke('trips:update', id, params),
  tripsDelete: (id) => ipcRenderer.invoke('trips:delete', id),
  tripsGetImages: (tripId) => ipcRenderer.invoke('trips:get-images', tripId),

  // Upload
  uploadStart: (params) => ipcRenderer.invoke('upload:start', params),
  uploadPause: () => ipcRenderer.invoke('upload:pause'),
  uploadResume: () => ipcRenderer.invoke('upload:resume'),
  uploadStatus: () => ipcRenderer.invoke('upload:status'),
  onUploadProgress: (callback) => {
    const listener = (_: Electron.IpcRendererEvent, progress: UploadProgressEvent) => callback(progress);
    ipcRenderer.on('upload:progress', listener);
    return () => ipcRenderer.removeListener('upload:progress', listener);
  },

  // Export
  exportCsv: (params) => ipcRenderer.invoke('export:csv', params),

  // Settings
  settingsGet: () => ipcRenderer.invoke('settings:get'),
  settingsSet: (settings) => ipcRenderer.invoke('settings:set', settings),

  // Backup
  backupTrigger: () => ipcRenderer.invoke('backup:trigger'),

  // Analytics
  imagesAnalytics: () => ipcRenderer.invoke('images:analytics'),

  // File system
  selectDirectory: () => ipcRenderer.invoke('fs:select-directory'),
  selectFile: (filters) => ipcRenderer.invoke('fs:select-file', filters),
  getThumbnailPath: (imagePath) => ipcRenderer.invoke('fs:get-thumbnail', imagePath),
};

contextBridge.exposeInMainWorld('electronAPI', api);
