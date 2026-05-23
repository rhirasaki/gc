import React, { useState, useCallback, useRef } from 'react';
import { PhotoImage, FileTypeFilter, SortBy, SortOrder, ImagesListParams } from '../../types';
import { useImages } from '../../hooks/useImages';
import ImageCard from './ImageCard';
import LightboxModal from './LightboxModal';
import FilterBar from './FilterBar';
import BatchActions from './BatchActions';

interface ImageGridProps {
  albumId?: number;
  tripId?: number;
}

const PAGE_SIZE = 60;

const ImageGrid: React.FC<ImageGridProps> = ({ albumId, tripId }) => {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [fileType, setFileType] = useState<FileTypeFilter>('ALL');
  const [sortBy, setSortBy] = useState<SortBy>('date_taken');
  const [sortOrder, setSortOrder] = useState<SortOrder>('DESC');
  const [showFlagged, setShowFlagged] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [lightboxImage, setLightboxImage] = useState<PhotoImage | null>(null);
  const lastSelectedRef = useRef<number | null>(null);

  const params: ImagesListParams = {
    page,
    pageSize: PAGE_SIZE,
    fileType,
    albumId,
    tripId,
    sortBy,
    sortOrder,
    flagged: showFlagged || undefined,
    search: search || undefined,
  };

  const { data, isLoading, isError } = useImages(params);
  const images = data?.images || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleSelect = useCallback((id: number, shift: boolean) => {
    setSelectedIds((prev) => {
      if (shift && lastSelectedRef.current !== null) {
        const imgIds = images.map((img) => img.id);
        const lastIdx = imgIds.indexOf(lastSelectedRef.current);
        const currIdx = imgIds.indexOf(id);
        const [start, end] = lastIdx < currIdx ? [lastIdx, currIdx] : [currIdx, lastIdx];
        const rangeIds = imgIds.slice(start, end + 1);
        const newSet = new Set([...prev, ...rangeIds]);
        return Array.from(newSet);
      }
      const exists = prev.includes(id);
      lastSelectedRef.current = exists ? null : id;
      return exists ? prev.filter((i) => i !== id) : [...prev, id];
    });
  }, [images]);

  const handleImageClick = useCallback((image: PhotoImage) => {
    setLightboxImage(image);
  }, []);

  const lightboxIndex = lightboxImage ? images.findIndex((img) => img.id === lightboxImage.id) : -1;

  const handleNext = useCallback(() => {
    if (lightboxIndex < images.length - 1) {
      setLightboxImage(images[lightboxIndex + 1]);
    }
  }, [lightboxIndex, images]);

  const handlePrev = useCallback(() => {
    if (lightboxIndex > 0) {
      setLightboxImage(images[lightboxIndex - 1]);
    }
  }, [lightboxIndex, images]);

  const handleSearchChange = useCallback((v: string) => { setSearch(v); setPage(1); }, []);
  const handleFileTypeChange = useCallback((v: FileTypeFilter) => { setFileType(v); setPage(1); }, []);
  const handleSortByChange = useCallback((v: SortBy) => { setSortBy(v); setPage(1); }, []);
  const handleSortOrderChange = useCallback((v: SortOrder) => { setSortOrder(v); setPage(1); }, []);
  const handleShowFlaggedChange = useCallback((v: boolean) => { setShowFlagged(v); setPage(1); }, []);

  return (
    <div className="flex flex-col h-full">
      <FilterBar
        search={search}
        onSearchChange={handleSearchChange}
        fileType={fileType}
        onFileTypeChange={handleFileTypeChange}
        sortBy={sortBy}
        onSortByChange={handleSortByChange}
        sortOrder={sortOrder}
        onSortOrderChange={handleSortOrderChange}
        showFlagged={showFlagged}
        onShowFlaggedChange={handleShowFlaggedChange}
        totalCount={total}
        selectedCount={selectedIds.length}
      />

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="flex items-center gap-3 text-gray-500">
              <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
              <span>Loading photos...</span>
            </div>
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center h-48 text-red-400">
            Failed to load photos. Please try again.
          </div>
        ) : images.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-500">
            <svg className="w-16 h-16 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <div className="font-medium">No photos found</div>
            <div className="text-sm mt-1">Import photos to get started</div>
          </div>
        ) : (
          <>
            {/* Select all bar */}
            {images.length > 0 && (
              <div className="flex items-center gap-3 mb-3">
                <button
                  onClick={() => {
                    if (selectedIds.length === images.length) {
                      setSelectedIds([]);
                    } else {
                      setSelectedIds(images.map((img) => img.id));
                    }
                  }}
                  className="text-xs text-gray-500 hover:text-white transition-colors"
                >
                  {selectedIds.length === images.length ? 'Deselect all' : 'Select all'}
                </button>
              </div>
            )}

            {/* Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
              {images.map((image) => (
                <ImageCard
                  key={image.id}
                  image={image}
                  selected={selectedIds.includes(image.id)}
                  onSelect={handleSelect}
                  onClick={handleImageClick}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm bg-gray-800 text-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-700 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-500">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 text-sm bg-gray-800 text-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-700 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Batch actions */}
      <BatchActions
        selectedIds={selectedIds}
        onClearSelection={() => setSelectedIds([])}
      />

      {/* Lightbox */}
      {lightboxImage && (
        <LightboxModal
          image={lightboxImage}
          onClose={() => setLightboxImage(null)}
          onNext={lightboxIndex < images.length - 1 ? handleNext : undefined}
          onPrev={lightboxIndex > 0 ? handlePrev : undefined}
        />
      )}
    </div>
  );
};

export default ImageGrid;
