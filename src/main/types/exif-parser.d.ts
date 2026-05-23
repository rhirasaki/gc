declare module 'exif-parser' {
  interface ExifTags {
    Make?: string;
    Model?: string;
    ISO?: number;
    FNumber?: number;
    ExposureTime?: number;
    FocalLength?: number;
    LensModel?: string;
    DateTimeOriginal?: number;
    DateTime?: number;
    GPSLatitude?: number;
    GPSLongitude?: number;
    [key: string]: unknown;
  }

  interface ExifResult {
    tags: ExifTags;
    imageSize?: { width: number; height: number };
  }

  interface Parser {
    enableSimpleValues(enabled: boolean): Parser;
    parse(): ExifResult;
  }

  function create(buffer: Buffer): Parser;
  export = { create };
}
