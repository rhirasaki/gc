import React, { useState } from 'react';
import TripList from '../components/Trips/TripList';
import TripDetail from '../components/Trips/TripDetail';

const TripsPage: React.FC = () => {
  const [selectedTripId, setSelectedTripId] = useState<number | null>(null);

  return (
    <div className="flex h-full">
      <TripList
        selectedTripId={selectedTripId}
        onSelectTrip={setSelectedTripId}
      />
      <div className="flex-1 min-w-0">
        {selectedTripId ? (
          <TripDetail tripId={selectedTripId} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <svg className="w-16 h-16 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            <div className="font-medium text-lg">Select a trip</div>
            <div className="text-sm mt-1">or create a new one to get started</div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TripsPage;
