import React from 'react';
import ImageGrid from '../Library/ImageGrid';

interface AlbumDetailProps {
  albumId: number | null;
}

const AlbumDetail: React.FC<AlbumDetailProps> = ({ albumId }) => {
  return <ImageGrid albumId={albumId ?? undefined} />;
};

export default AlbumDetail;
