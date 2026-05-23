import React, { useState, useEffect } from 'react';
import { PhotoImage } from '../../types';
import { formatDate, formatFileSize, formatDateTime } from '../../hooks/useImages';
import { useFlagImages } from '../../hooks/useImages';

interface LightboxModalProps {
  image: PhotoImage;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
}

const LightboxModal: React.FC<LightboxModalProps> = ({ image, onClose, onNext, onPrev }) => {
  const [imgError, setImgError] = useState(false);
  const [showMetadata, setShowMetadata] = useState(true);
  const flagMutation = useFlagImages();

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') onNext?.();
      if (e.key === 'ArrowLeft') onPrev?.();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose, onNext, onPrev]);

  const hasDoNotUpload = image.flags.some((f) => f.flagType === 'DO_NOT_UPLOAD');
  const isFlagged = image.flags.some((f) => f.flagType === 'FLAGGED_FOR_REVIEW');
  const isRaw = image.fileType === 'RAW';

  const toggleFlag = async (flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW', current: boolean) => {
    await flagMutation.mutateAsync({
      imageIds: [image.id],
      flagType,
      action: current ? 'unset' : 'set',
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/95 flex"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Image area */}
      <div className="flex-1 flex items-center justify-center relative p-4">
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-gray-400 hover:text-white bg-black/50 rounded-lg z-10"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Nav buttons */}
        {onPrev && (
          <button
            onClick={onPrev}
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-gray-400 hover:text-white bg-black/50 hover:bg-black/80 rounded-full z-10 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        )}
        {onNext && (
          <button
            onClick={onNext}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-3 text-gray-400 hover:text-white bg-black/50 hover:bg-black/80 rounded-full z-10 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}

        {/* Image */}
        {!imgError ? (
          <img
            src={`file://${image.filepath}`}
            alt={image.filename}
            className="max-w-full max-h-full object-contain rounded-lg"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-4 text-gray-500">
            <svg className="w-24 h-24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <div className="text-center">
              <div className="text-white font-medium">{image.filename}</div>
              <div className="text-sm mt-1">Preview not available for {image.fileType} files</div>
            </div>
          </div>
        )}

        {/* Toggle metadata panel */}
        <button
          onClick={() => setShowMetadata(!showMetadata)}
          className="absolute bottom-4 right-4 p-2 text-gray-400 hover:text-white bg-black/50 rounded-lg z-10"
          title="Toggle metadata panel"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
      </div>

      {/* Metadata panel */}
      {showMetadata && (
        <div className="w-72 bg-gray-900 border-l border-gray-800 flex flex-col overflow-y-auto">
          <div className="p-4 border-b border-gray-800">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-white font-medium text-sm break-all">{image.filename}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className={isRaw ? 'badge-raw' : 'badge-jpg'}>{image.fileType}</span>
                  {image.uploadedAt && <span className="badge-uploaded">Uploaded</span>}
                </div>
              </div>
            </div>
          </div>

          {/* EXIF Data */}
          <div className="p-4 space-y-4">
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">File Info</h3>
              <dl className="space-y-1">
                <MetaRow label="Size" value={formatFileSize(image.fileSize)} />
                <MetaRow label="Added" value={formatDateTime(image.createdAt)} />
                {image.uploadedAt && <MetaRow label="Uploaded" value={formatDateTime(image.uploadedAt)} />}
              </dl>
            </div>

            {(image.metadata.cameraModel || image.metadata.iso) && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Camera</h3>
                <dl className="space-y-1">
                  {image.metadata.cameraModel && <MetaRow label="Camera" value={image.metadata.cameraModel} />}
                  {image.metadata.lensInfo && <MetaRow label="Lens" value={image.metadata.lensInfo} />}
                  {image.metadata.iso && <MetaRow label="ISO" value={String(image.metadata.iso)} />}
                  {image.metadata.aperture && <MetaRow label="Aperture" value={`f/${image.metadata.aperture}`} />}
                  {image.metadata.shutterSpeed && <MetaRow label="Shutter" value={image.metadata.shutterSpeed} />}
                  {image.metadata.focalLength && <MetaRow label="Focal Length" value={`${image.metadata.focalLength}mm`} />}
                </dl>
              </div>
            )}

            {image.metadata.dateTaken && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Date & Location</h3>
                <dl className="space-y-1">
                  <MetaRow label="Taken" value={formatDateTime(image.metadata.dateTaken)} />
                  {image.metadata.latitude && image.metadata.longitude && (
                    <MetaRow
                      label="GPS"
                      value={`${image.metadata.latitude.toFixed(4)}, ${image.metadata.longitude.toFixed(4)}`}
                    />
                  )}
                  {image.metadata.cityCluster && <MetaRow label="Location" value={image.metadata.cityCluster} />}
                </dl>
              </div>
            )}

            {image.albums.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Albums</h3>
                <div className="flex flex-wrap gap-1">
                  {image.albums.map((a) => (
                    <span key={a.id} className="text-xs px-2 py-0.5 bg-gray-800 text-gray-300 rounded-full">
                      {a.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Actions</h3>
              <div className="space-y-2">
                <button
                  onClick={() => toggleFlag('DO_NOT_UPLOAD', hasDoNotUpload)}
                  className={`w-full px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 ${
                    hasDoNotUpload
                      ? 'bg-red-700/30 text-red-400 hover:bg-red-700/50'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
                  }`}
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
                  </svg>
                  {hasDoNotUpload ? 'Remove No-Upload Flag' : 'Mark: Do Not Upload'}
                </button>

                <button
                  onClick={() => toggleFlag('FLAGGED_FOR_REVIEW', isFlagged)}
                  className={`w-full px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 ${
                    isFlagged
                      ? 'bg-yellow-700/30 text-yellow-400 hover:bg-yellow-700/50'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
                  }`}
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 7l2.55 2.4A1 1 0 0116 11H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z" clipRule="evenodd" />
                  </svg>
                  {isFlagged ? 'Remove Review Flag' : 'Flag for Review'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const MetaRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex gap-2">
    <dt className="text-xs text-gray-500 w-20 flex-shrink-0">{label}</dt>
    <dd className="text-xs text-gray-300 flex-1 break-all">{value}</dd>
  </div>
);

export default LightboxModal;
