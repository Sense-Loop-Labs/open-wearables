/**
 * Sense Loop Settings Hooks
 * React Query hooks for organization settings management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slSettingsService } from '@/lib/api/services/sense-loop.service';
import type { SettingsUpdate } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { queryKeys } from '@/lib/query/keys';

export function useSlSettings(organizationId?: string) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.settings.current(orgId),
    queryFn: () => slSettingsService.get(orgId),
    staleTime: 60 * 1000, // 1 minute
  });
}

export function useUpdateSlSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      data,
      organizationId,
    }: {
      data: SettingsUpdate;
      organizationId?: string;
    }) => slSettingsService.update(data, organizationId),
    onSuccess: (_, { organizationId }) => {
      const orgId = organizationId || getSlCurrentOrgId() || undefined;
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.settings.current(orgId),
      });
      toast.success('Settings updated successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update settings');
    },
  });
}
