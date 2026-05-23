import React from 'react';
import ImageGrid from '../Library/ImageGrid';
import { useTrips } from '../../hooks/useAlbums';
import { formatDate } from '../../hooks/useImages';

interface TripDetailProps {
  tripId: number | null;
}

const TripDetail: React.FC<TripDetailProps> = ({ tripId }) => {
  const { data: trips } = useTrips();
  const trip = trips?.find((t) => t.id === tripId);

  return (
    <div className="flex flex-col h-full">
      {trip && (
        <div className="px-6 py-4 border-b border-gray-800 bg-gray-900 flex-shrink-0">
          <h2 className="text-white font-semibold text-lg">{trip.name}</h2>
          <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
            {trip.startDate && (
              <span>{formatDate(trip.startDate)} – {trip.endDate ? formatDate(trip.endDate) : 'Present'}</span>
            )}
            <span>{trip.imageCount ?? 0} photos</span>
            <span>{trip.albumCount ?? 0} albums</span>
          </div>
          {trip.description && (
            <p className="text-sm text-gray-400 mt-2">{trip.description}</p>
          )}
        </div>
      )}
      <div className="flex-1 overflow-hidden">
        <ImageGrid tripId={tripId ?? undefined} />
      </div>
    </div>
  );
};

export default TripDetail;
