import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const api = window.electronAPI;

export function useAlbums() {
  return useQuery({
    queryKey: ['albums'],
    queryFn: () => api.albumsList(),
  });
}

export function useAlbumImages(albumId: number | null) {
  return useQuery({
    queryKey: ['album-images', albumId],
    queryFn: () => (albumId ? api.albumsGetImages(albumId) : []),
    enabled: albumId !== null,
  });
}

export function useCreateAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { name: string; tripId?: number }) => api.albumsCreate(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
  });
}

export function useAssignAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      imageIds: number[];
      albumId: number;
      action: 'assign' | 'unassign';
    }) => api.albumsAssign(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      queryClient.invalidateQueries({ queryKey: ['album-images'] });
      queryClient.invalidateQueries({ queryKey: ['images'] });
    },
  });
}

export function useRemoveAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (albumId: number) => api.albumsRemove(albumId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
  });
}

export function useTrips() {
  return useQuery({
    queryKey: ['trips'],
    queryFn: () => api.tripsList(),
  });
}

export function useTripImages(tripId: number | null) {
  return useQuery({
    queryKey: ['trip-images', tripId],
    queryFn: () => (tripId ? api.tripsGetImages(tripId) : []),
    enabled: tripId !== null,
  });
}

export function useCreateTrip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      name: string;
      startDate?: string;
      endDate?: string;
      description?: string;
    }) => api.tripsCreate(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trips'] });
    },
  });
}

export function useUpdateTrip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, params }: {
      id: number;
      params: { name?: string; startDate?: string; endDate?: string; description?: string };
    }) => api.tripsUpdate(id, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trips'] });
    },
  });
}

export function useDeleteTrip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.tripsDelete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trips'] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
  });
}
