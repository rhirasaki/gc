import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ImagesListParams, PhotoImage } from '../types';
import type { AnalyticsData } from '../types/electron.d';

const api = window.electronAPI;

export function useImages(params: ImagesListParams) {
  return useQuery({
    queryKey: ['images', params],
    queryFn: () => api.imagesList(params),
    placeholderData: (prev) => prev,
  });
}

export function useImage(id: number | null) {
  return useQuery({
    queryKey: ['image', id],
    queryFn: () => (id ? api.imagesGet(id) : null),
    enabled: id !== null,
  });
}

export function useFlagImages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      imageIds: number[];
      flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW';
      action: 'set' | 'unset';
      reason?: string;
    }) => api.imagesFlag(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['images'] });
      queryClient.invalidateQueries({ queryKey: ['image'] });
    },
  });
}

export function useDeleteImages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) => api.imagesDelete(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['images'] });
    },
  });
}

export function useAnalytics() {
  return useQuery<AnalyticsData | null>({
    queryKey: ['analytics'],
    queryFn: () => api.imagesAnalytics(),
    staleTime: 60000,
  });
}

export function formatFileSize(bytes: number | null): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export function getImageFlagTypes(image: PhotoImage): string[] {
  return image.flags.map((f) => f.flagType);
}

export function hasFlag(image: PhotoImage, flagType: 'DO_NOT_UPLOAD' | 'FLAGGED_FOR_REVIEW'): boolean {
  return image.flags.some((f) => f.flagType === flagType);
}
