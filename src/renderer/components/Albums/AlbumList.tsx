import React, { useState } from 'react';
import { Album } from '../../types';
import { useAlbums, useCreateAlbum, useRemoveAlbum } from '../../hooks/useAlbums';

interface AlbumListProps {
  selectedAlbumId: number | null;
  onSelectAlbum: (id: number | null) => void;
}

const AlbumList: React.FC<AlbumListProps> = ({ selectedAlbumId, onSelectAlbum }) => {
  const { data: albums, isLoading } = useAlbums();
  const createAlbum = useCreateAlbum();
  const removeAlbum = useRemoveAlbum();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await createAlbum.mutateAsync({ name: newName.trim() });
    setNewName('');
    setShowCreate(false);
  };

  const handleRemove = async (album: Album, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Remove album "${album.name}"? Photos will not be deleted.`)) return;
    await removeAlbum.mutateAsync(album.id);
    if (selectedAlbumId === album.id) onSelectAlbum(null);
  };

  return (
    <div className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col h-full flex-shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-sm font-medium text-gray-300">Albums</span>
        <button
          onClick={() => setShowCreate(true)}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {showCreate && (
        <div className="p-3 border-b border-gray-800">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Album name..."
            autoFocus
            className="input-field text-sm py-1.5"
          />
          <div className="flex gap-2 mt-2">
            <button onClick={handleCreate} className="btn-primary text-xs py-1 flex-1">Create</button>
            <button onClick={() => { setShowCreate(false); setNewName(''); }} className="btn-ghost text-xs py-1">Cancel</button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto py-2">
        <button
          onClick={() => onSelectAlbum(null)}
          className={`w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
            selectedAlbumId === null ? 'text-blue-400 bg-blue-600/10' : 'text-gray-400 hover:text-white hover:bg-gray-800'
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          All Photos
        </button>

        {isLoading ? (
          <div className="px-4 py-2 text-xs text-gray-600">Loading...</div>
        ) : (
          albums?.map((album) => (
            <div
              key={album.id}
              onClick={() => onSelectAlbum(album.id)}
              className={`group flex items-center gap-3 px-4 py-2 text-sm cursor-pointer transition-colors ${
                selectedAlbumId === album.id ? 'text-blue-400 bg-blue-600/10' : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <div className="flex-1 min-w-0">
                <div className="truncate">{album.name}</div>
                <div className="text-xs text-gray-600">{album.imageCount ?? 0} photos</div>
              </div>
              <button
                onClick={(e) => handleRemove(album, e)}
                className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-0.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default AlbumList;
