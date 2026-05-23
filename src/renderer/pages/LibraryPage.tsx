import React, { useState } from 'react';
import AlbumList from '../components/Albums/AlbumList';
import ImageGrid from '../components/Library/ImageGrid';

const LibraryPage: React.FC = () => {
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);

  return (
    <div className="flex h-full">
      <AlbumList
        selectedAlbumId={selectedAlbumId}
        onSelectAlbum={setSelectedAlbumId}
      />
      <div className="flex-1 min-w-0">
        <ImageGrid albumId={selectedAlbumId ?? undefined} />
      </div>
    </div>
  );
};

export default LibraryPage;
