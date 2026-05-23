import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { UploadProgressEvent } from '../types';

const api = window.electronAPI;

export function useUploadStatus() {
  return useQuery({
    queryKey: ['upload-status'],
    queryFn: () => api.uploadStatus(),
    refetchInterval: 3000,
  });
}

export function useUploadStart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      imageIds?: number[];
      albumId?: number;
      remote: string;
      remotePath: string;
      rclonePath?: string;
    }) => api.uploadStart(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['upload-status'] });
    },
  });
}

export function useUploadProgress() {
  const [progressItems, setProgressItems] = useState<Map<number, UploadProgressEvent>>(new Map());

  useEffect(() => {
    const unsubscribe = api.onUploadProgress((progress) => {
      setProgressItems((prev) => {
        const next = new Map(prev);
        next.set(progress.imageId, progress);
        // Remove done items after a delay
        if (progress.status === 'done') {
          setTimeout(() => {
            setProgressItems((p) => {
              const n = new Map(p);
              n.delete(progress.imageId);
              return n;
            });
          }, 2000);
        }
        return next;
      });
    });

    return unsubscribe;
  }, []);

  return Array.from(progressItems.values());
}

export function useUploadControls() {
  const queryClient = useQueryClient();

  const pause = useCallback(async () => {
    await api.uploadPause();
    queryClient.invalidateQueries({ queryKey: ['upload-status'] });
  }, [queryClient]);

  const resume = useCallback(async () => {
    await api.uploadResume();
    queryClient.invalidateQueries({ queryKey: ['upload-status'] });
  }, [queryClient]);

  return { pause, resume };
}
