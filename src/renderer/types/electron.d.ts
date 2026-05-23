// Type declaration for window.electronAPI
// The actual interface is defined in src/main/preload.ts

export interface AnalyticsData {
  totalImages: number;
  rawCount: number;
  jpgCount: number;
  uploadedCount: number;
  withLocation: number;
  byCamera: { camera_model: string; count: number }[];
  byDate: { month: string; count: number }[];
}

export interface ElectronAPIType {
  // Import
  importScan: (directory: string) => Promise<import('./index').ScanResult>;
  importConfirm: (params: {
    files: import('./index').ScannedFile[];
    destinationDir: string;
  }) => Promise<{ success: boolean; processed: number; errors: string[] }>;
  importDeleteFromSD: (filepaths: string[]) => Promise<{ success: boolean; deleted: string[]; errors: string[] }>;
  onImportScanProgress: (callback: (progress: { total: number; processed: number; currentFile: string }) => void) => () => void;
  onImportConfirmProgress: (callback: (progress: { total: number; processed: number; currentFile: string }) => void) => () => void;

  // Images
  imagesList: (params: import('./index').ImagesListParams) => Promise<import('./index').ImagesListResult>;
  imagesGet: (id: number) => Promise<import('./index').PhotoImage | null>;
  imagesFlag: (params: {
    imageIds: number[];
    flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW';
    action: 'set' | 'unset';
    reason?: string;
  }) => Promise<{ success: boolean; updated: number }>;
  imagesDelete: (ids: number[]) => Promise<{ success: boolean; deleted: string[]; errors: string[] }>;
  imagesUpdateMetadata: (id: number, metadata: Partial<import('./index').ImageMetadata>) => Promise<void>;
  imagesAnalytics: () => Promise<AnalyticsData>;

  // Albums
  albumsList: () => Promise<import('./index').Album[]>;
  albumsCreate: (params: { name: string; tripId?: number }) => Promise<import('./index').Album>;
  albumsAssign: (params: {
    imageIds: number[];
    albumId: number;
    action: 'assign' | 'unassign';
  }) => Promise<void>;
  albumsRemove: (albumId: number) => Promise<void>;
  albumsGetImages: (albumId: number) => Promise<import('./index').PhotoImage[]>;

  // Trips
  tripsList: () => Promise<import('./index').Trip[]>;
  tripsCreate: (params: {
    name: string;
    startDate?: string;
    endDate?: string;
    description?: string;
  }) => Promise<import('./index').Trip>;
  tripsUpdate: (id: number, params: {
    name?: string;
    startDate?: string;
    endDate?: string;
    description?: string;
  }) => Promise<import('./index').Trip>;
  tripsDelete: (id: number) => Promise<void>;
  tripsGetImages: (tripId: number) => Promise<import('./index').PhotoImage[]>;

  // Upload
  uploadStart: (params: {
    imageIds?: number[];
    albumId?: number;
    remote: string;
    remotePath: string;
    rclonePath?: string;
  }) => Promise<{ success: boolean; queued: number }>;
  uploadPause: () => Promise<void>;
  uploadResume: () => Promise<void>;
  uploadStatus: () => Promise<import('./index').UploadStatus>;
  onUploadProgress: (callback: (progress: import('./index').UploadProgressEvent) => void) => () => void;

  // Export
  exportCsv: (params: import('./index').ExportCsvParams) => Promise<import('./index').ExportResult>;

  // Settings
  settingsGet: () => Promise<import('./index').AppSettings>;
  settingsSet: (settings: Partial<import('./index').AppSettings>) => Promise<void>;

  // Backup
  backupTrigger: () => Promise<{ success: number; failed: number; errors: string[] }>;

  // File system
  selectDirectory: () => Promise<string | null>;
  selectFile: (filters?: { name: string; extensions: string[] }[]) => Promise<string | null>;
  getThumbnailPath: (imagePath: string) => Promise<string>;
}

declare global {
  interface Window {
    electronAPI: ElectronAPIType;
  }
}
