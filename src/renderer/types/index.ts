// Core data types for the photo organizer

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

export interface Album {
  id: number;
  name: string;
  tripId: number | null;
  createdAt: string;
  imageCount?: number;
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

export interface PhotoImage {
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

export interface ImagesListResult {
  images: PhotoImage[];
  total: number;
  page: number;
  pageSize: number;
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

export interface ScanResult {
  success: boolean;
  files?: ScannedFile[];
  pairs?: PairInfo[];
  total?: number;
  error?: string;
}

export interface ImportResult {
  success: boolean;
  processed: number;
  errors: string[];
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

export interface AppSettings {
  libraryPath: string;
  rcloneRemote: string;
  rcloneRemotePath: string;
  rclonePath: string;
  autoImportEnabled: boolean;
  thumbnailSize: number;
  theme: 'dark' | 'light';
}

export interface ExportCsvParams {
  albumId?: number;
  tripId?: number;
  startDate?: string;
  endDate?: string;
  fileType?: 'RAW' | 'JPG' | 'ALL';
  outputPath?: string;
}

export interface ExportResult {
  success: boolean;
  rowsExported: number;
  outputPath: string;
  error?: string;
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

export type SortBy = 'date_taken' | 'filename' | 'file_size' | 'created_at';
export type SortOrder = 'ASC' | 'DESC';
export type FileTypeFilter = 'RAW' | 'JPG' | 'ALL';

export interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
}
