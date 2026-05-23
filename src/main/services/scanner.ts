import fg from 'fast-glob';
import * as fs from 'fs';
import * as path from 'path';
import ExifParser from 'exif-parser';
import { computeMD5 } from './hasher';

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

export interface ScanProgress {
  total: number;
  processed: number;
  currentFile: string;
  files?: ScannedFile[];
}

const RAW_EXTENSIONS = ['.raf', '.RAF', '.cr2', '.CR2', '.nef', '.NEF', '.arw', '.ARW', '.dng', '.DNG', '.orf', '.ORF', '.rw2', '.RW2'];
const JPG_EXTENSIONS = ['.jpg', '.JPG', '.jpeg', '.JPEG'];

function isRaw(ext: string): boolean {
  return RAW_EXTENSIONS.includes(ext);
}

function isJpg(ext: string): boolean {
  return JPG_EXTENSIONS.includes(ext);
}

function extractExif(filepath: string): ScannedFile['metadata'] {
  try {
    const buffer = fs.readFileSync(filepath);
    const parser = ExifParser.create(buffer);
    parser.enableSimpleValues(true);
    const result = parser.parse();
    const tags = result.tags;

    let dateTaken: string | undefined;
    if (tags.DateTimeOriginal) {
      const ts = tags.DateTimeOriginal as number;
      dateTaken = new Date(ts * 1000).toISOString();
    } else if (tags.DateTime) {
      const ts = tags.DateTime as number;
      dateTaken = new Date(ts * 1000).toISOString();
    }

    let shutterSpeed: string | undefined;
    if (tags.ExposureTime) {
      const et = tags.ExposureTime as number;
      if (et < 1) {
        shutterSpeed = `1/${Math.round(1 / et)}`;
      } else {
        shutterSpeed = `${et}s`;
      }
    }

    let latitude: number | undefined;
    let longitude: number | undefined;
    if (result.tags.GPSLatitude !== undefined && result.tags.GPSLongitude !== undefined) {
      latitude = result.tags.GPSLatitude as number;
      longitude = result.tags.GPSLongitude as number;
    }

    return {
      cameraMake: tags.Make as string | undefined,
      cameraModel: tags.Model as string | undefined,
      iso: tags.ISO as number | undefined,
      aperture: tags.FNumber as number | undefined,
      shutterSpeed,
      focalLength: tags.FocalLength as number | undefined,
      lensInfo: tags.LensModel as string | undefined,
      dateTaken,
      latitude,
      longitude,
    };
  } catch {
    return {};
  }
}

export async function scanDirectory(
  directory: string,
  onProgress: (progress: ScanProgress) => void
): Promise<ScannedFile[]> {
  const patterns = [
    '**/*.raf', '**/*.RAF',
    '**/*.cr2', '**/*.CR2',
    '**/*.nef', '**/*.NEF',
    '**/*.arw', '**/*.ARW',
    '**/*.dng', '**/*.DNG',
    '**/*.orf', '**/*.ORF',
    '**/*.rw2', '**/*.RW2',
    '**/*.jpg', '**/*.JPG',
    '**/*.jpeg', '**/*.JPEG',
  ];

  const allFiles = await fg(patterns, {
    cwd: directory,
    absolute: true,
    caseSensitiveMatch: false,
  });

  const total = allFiles.length;
  const scannedFiles: ScannedFile[] = [];

  for (let i = 0; i < allFiles.length; i++) {
    const filepath = allFiles[i];
    const filename = path.basename(filepath);
    const ext = path.extname(filepath);

    onProgress({
      total,
      processed: i,
      currentFile: filename,
    });

    try {
      const stat = fs.statSync(filepath);
      const fileHash = await computeMD5(filepath);
      const metadata = isJpg(ext) ? extractExif(filepath) : {};

      const scannedFile: ScannedFile = {
        filename,
        filepath,
        fileType: isRaw(ext) ? 'RAW' : 'JPG',
        fileSize: stat.size,
        fileHash,
        metadata,
      };

      scannedFiles.push(scannedFile);
    } catch (err) {
      console.error(`Error scanning file ${filepath}:`, err);
    }
  }

  onProgress({
    total,
    processed: total,
    currentFile: '',
    files: scannedFiles,
  });

  return scannedFiles;
}

export function detectPairs(files: ScannedFile[]): Map<string, { raw?: ScannedFile; jpg?: ScannedFile }> {
  const pairs = new Map<string, { raw?: ScannedFile; jpg?: ScannedFile }>();

  for (const file of files) {
    const baseName = path.basename(file.filename, path.extname(file.filename)).toUpperCase();
    const existing = pairs.get(baseName) || {};

    if (file.fileType === 'RAW') {
      pairs.set(baseName, { ...existing, raw: file });
    } else {
      pairs.set(baseName, { ...existing, jpg: file });
    }
  }

  return pairs;
}
