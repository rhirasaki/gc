import React, { useState } from 'react';
import { Trip } from '../../types';
import { useTrips, useCreateTrip, useDeleteTrip } from '../../hooks/useAlbums';
import { formatDate } from '../../hooks/useImages';

interface TripListProps {
  selectedTripId: number | null;
  onSelectTrip: (id: number | null) => void;
}

const TripList: React.FC<TripListProps> = ({ selectedTripId, onSelectTrip }) => {
  const { data: trips, isLoading } = useTrips();
  const createTrip = useCreateTrip();
  const deleteTrip = useDeleteTrip();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', startDate: '', endDate: '', description: '' });

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    await createTrip.mutateAsync({
      name: form.name.trim(),
      startDate: form.startDate || undefined,
      endDate: form.endDate || undefined,
      description: form.description || undefined,
    });
    setForm({ name: '', startDate: '', endDate: '', description: '' });
    setShowCreate(false);
  };

  const handleDelete = async (trip: Trip, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete trip "${trip.name}"? Albums will not be deleted.`)) return;
    await deleteTrip.mutateAsync(trip.id);
    if (selectedTripId === trip.id) onSelectTrip(null);
  };

  return (
    <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full flex-shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-sm font-medium text-gray-300">Trips</span>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {showCreate && (
        <div className="p-3 border-b border-gray-800 space-y-2">
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Trip name"
            autoFocus
            className="input-field text-sm py-1.5"
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((f) => ({ ...f, startDate: e.target.value }))}
              className="input-field text-xs py-1.5"
              placeholder="Start date"
            />
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((f) => ({ ...f, endDate: e.target.value }))}
              className="input-field text-xs py-1.5"
              placeholder="End date"
            />
          </div>
          <textarea
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description (optional)"
            rows={2}
            className="input-field text-xs resize-none"
          />
          <div className="flex gap-2">
            <button onClick={handleCreate} className="btn-primary text-xs py-1 flex-1">Create</button>
            <button onClick={() => setShowCreate(false)} className="btn-ghost text-xs py-1">Cancel</button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto py-2">
        <button
          onClick={() => onSelectTrip(null)}
          className={`w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
            selectedTripId === null ? 'text-blue-400 bg-blue-600/10' : 'text-gray-400 hover:text-white hover:bg-gray-800'
          }`}
        >
          All Trips
        </button>

        {isLoading ? (
          <div className="px-4 py-2 text-xs text-gray-600">Loading...</div>
        ) : trips?.length === 0 ? (
          <div className="px-4 py-4 text-xs text-gray-600 text-center">
            No trips yet. Create one to organize your travels.
          </div>
        ) : (
          trips?.map((trip) => (
            <div
              key={trip.id}
              onClick={() => onSelectTrip(trip.id)}
              className={`group flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                selectedTripId === trip.id ? 'text-blue-400 bg-blue-600/10' : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <div className="w-8 h-8 bg-blue-900/30 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{trip.name}</div>
                {trip.startDate && (
                  <div className="text-xs text-gray-600 mt-0.5">
                    {formatDate(trip.startDate)}
                    {trip.endDate && ` – ${formatDate(trip.endDate)}`}
                  </div>
                )}
                <div className="text-xs text-gray-600">
                  {trip.imageCount ?? 0} photos · {trip.albumCount ?? 0} albums
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(trip, e)}
                className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-0.5 mt-1"
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

export default TripList;
