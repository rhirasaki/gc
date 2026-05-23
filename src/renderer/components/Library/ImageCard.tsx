import React, { useState } from 'react';
import { PhotoImage } from '../../types';
import { formatDate, formatFileSize } from '../../hooks/useImages';

interface ImageCardProps {
  image: PhotoImage;
  selected: boolean;
  onSelect: (id: number, shift: boolean) => void;
  onClick: (image: PhotoImage) => void;
}

const ImageCard: React.FC<ImageCardProps> = ({ image, selected, onSelect, onClick }) => {
  const [imgError, setImgError] = useState(false);
  const thumbnailUrl = `file://${image.filepath}`;
  const isRaw = image.fileType === 'RAW';
  const hasDoNotUpload = image.flags.some((f) => f.flagType === 'DO_NOT_UPLOAD');
  const isFlagged = image.flags.some((f) => f.flagType === 'FLAGGED_FOR_REVIEW');
  const isUploaded = !!image.uploadedAt;

  const handleClick = (e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
      onSelect(image.id, e.shiftKey);
    } else {
      onClick(image);
    }
  };

  const handleCheckbox = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(image.id, e.shiftKey);
  };

  return (
    <div
      className={`relative group cursor-pointer rounded-lg overflow-hidden bg-gray-900 border transition-all duration-150 ${
        selected
          ? 'border-blue-500 ring-2 ring-blue-500/50'
          : 'border-gray-800 hover:border-gray-600'
      }`}
      onClick={handleClick}
    >
      {/* Thumbnail */}
      <div className="aspect-square bg-gray-800 relative">
        {!imgError ? (
          <img
            src={thumbnailUrl}
            alt={image.filename}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-10 h-10 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}

        {/* Overlay badges */}
        <div className="absolute top-2 left-2 flex gap-1">
          <span className={isRaw ? 'badge-raw' : 'badge-jpg'}>
            {image.fileType}
          </span>
          {isUploaded && <span className="badge-uploaded">✓</span>}
        </div>

        {/* Flag indicators */}
        <div className="absolute top-2 right-2 flex gap-1">
          {hasDoNotUpload && (
            <span className="text-xs px-1 py-0.5 bg-red-900/80 text-red-300 rounded" title="Do Not Upload">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
              </svg>
            </span>
          )}
          {isFlagged && (
            <span className="text-xs px-1 py-0.5 bg-yellow-900/80 text-yellow-300 rounded" title="Flagged for Review">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 7l2.55 2.4A1 1 0 0116 11H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </div>

        {/* Selection checkbox */}
        <div
          className={`absolute top-2 left-2 mt-0 ml-0 transition-opacity duration-150 ${
            selected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}
          onClick={handleCheckbox}
        >
          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
            selected ? 'bg-blue-500 border-blue-500' : 'bg-black/50 border-white/60 hover:border-white'
          }`}>
            {selected && (
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="p-2">
        <div className="text-xs text-gray-300 truncate font-mono" title={image.filename}>
          {image.filename}
        </div>
        <div className="text-xs text-gray-500 mt-0.5 flex items-center justify-between">
          <span>{formatDate(image.metadata.dateTaken)}</span>
          <span>{formatFileSize(image.fileSize)}</span>
        </div>
      </div>
    </div>
  );
};

export default ImageCard;
