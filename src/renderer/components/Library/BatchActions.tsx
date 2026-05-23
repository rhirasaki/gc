import React, { useState } from 'react';
import { useAlbums, useAssignAlbum } from '../../hooks/useAlbums';
import { useFlagImages, useDeleteImages } from '../../hooks/useImages';

interface BatchActionsProps {
  selectedIds: number[];
  onClearSelection: () => void;
}

const BatchActions: React.FC<BatchActionsProps> = ({ selectedIds, onClearSelection }) => {
  const [showAlbumMenu, setShowAlbumMenu] = useState(false);
  const { data: albums } = useAlbums();
  const flagMutation = useFlagImages();
  const deleteMutation = useDeleteImages();
  const assignMutation = useAssignAlbum();

  if (selectedIds.length === 0) return null;

  const handleFlag = async (flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW', action: 'set' | 'unset') => {
    await flagMutation.mutateAsync({ imageIds: selectedIds, flagType, action });
    onClearSelection();
  };

  const handleDelete = async () => {
    if (!confirm(`Delete ${selectedIds.length} image(s) from the library? This cannot be undone.`)) return;
    await deleteMutation.mutateAsync(selectedIds);
    onClearSelection();
  };

  const handleAssign = async (albumId: number) => {
    await assignMutation.mutateAsync({ imageIds: selectedIds, albumId, action: 'assign' });
    setShowAlbumMenu(false);
    onClearSelection();
  };

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-20">
      <div className="bg-gray-800 border border-gray-600 rounded-xl shadow-2xl px-4 py-3 flex items-center gap-3">
        <span className="text-white font-medium text-sm">
          {selectedIds.length} selected
        </span>

        <div className="w-px h-5 bg-gray-600" />

        {/* Flag DO_NOT_UPLOAD */}
        <button
          onClick={() => handleFlag('DO_NOT_UPLOAD', 'set')}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700/30 text-red-400 hover:bg-red-700/50 rounded-lg text-xs font-medium transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
          </svg>
          No Upload
        </button>

        {/* Flag for review */}
        <button
          onClick={() => handleFlag('FLAGGED_FOR_REVIEW', 'set')}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-700/30 text-yellow-400 hover:bg-yellow-700/50 rounded-lg text-xs font-medium transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 7l2.55 2.4A1 1 0 0116 11H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z" clipRule="evenodd" />
          </svg>
          Flag
        </button>

        {/* Clear flags */}
        <button
          onClick={() => {
            handleFlag('DO_NOT_UPLOAD', 'unset');
            handleFlag('FLAGGED_FOR_REVIEW', 'unset');
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 text-gray-300 hover:bg-gray-600 rounded-lg text-xs font-medium transition-colors"
        >
          Clear Flags
        </button>

        <div className="w-px h-5 bg-gray-600" />

        {/* Assign to album */}
        <div className="relative">
          <button
            onClick={() => setShowAlbumMenu(!showAlbumMenu)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-700/30 text-blue-400 hover:bg-blue-700/50 rounded-lg text-xs font-medium transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            Add to Album
          </button>
          {showAlbumMenu && (
            <div className="absolute bottom-full mb-2 left-0 bg-gray-800 border border-gray-700 rounded-lg shadow-xl py-1 min-w-[180px] z-10">
              {albums && albums.length > 0 ? albums.map((album) => (
                <button
                  key={album.id}
                  onClick={() => handleAssign(album.id)}
                  className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:text-white hover:bg-gray-700 transition-colors"
                >
                  {album.name}
                </button>
              )) : (
                <div className="px-4 py-2 text-xs text-gray-500">No albums yet</div>
              )}
            </div>
          )}
        </div>

        <div className="w-px h-5 bg-gray-600" />

        {/* Delete */}
        <button
          onClick={handleDelete}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-900/30 text-red-400 hover:bg-red-900/50 rounded-lg text-xs font-medium transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Delete
        </button>

        {/* Clear selection */}
        <button
          onClick={onClearSelection}
          className="p-1.5 text-gray-500 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default BatchActions;
