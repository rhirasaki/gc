import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AppSettings } from '../types';

const api = window.electronAPI;

const DEFAULT_SETTINGS: AppSettings = {
  libraryPath: '',
  rcloneRemote: 'gdrive',
  rcloneRemotePath: 'Photos',
  rclonePath: 'rclone',
  autoImportEnabled: false,
  thumbnailSize: 200,
  theme: 'dark',
};

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const settings = await api.settingsGet();
      return { ...DEFAULT_SETTINGS, ...settings } as AppSettings;
    },
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: Partial<AppSettings>) => api.settingsSet(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });
}
