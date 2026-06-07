/**
 * Sense Loop Alerts Hooks
 * React Query hooks for alert management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slAlertsService } from '@/lib/api/services/sense-loop.service';
import type {
  AlertAcknowledgeRequest,
  AlertQueryParams,
  AlertResolveRequest,
} from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { queryKeys } from '@/lib/query/keys';

export function useSlAlerts(params?: AlertQueryParams) {
  const orgId = params?.organization_id || getSlCurrentOrgId() || undefined;
  const queryParams = { ...params, organization_id: orgId };

  return useQuery({
    queryKey: queryKeys.sl.alerts.list(queryParams),
    queryFn: () => slAlertsService.getAll(queryParams),
    placeholderData: (previousData) => previousData,
    staleTime: 30 * 1000, // 30 seconds - alerts should refresh frequently
  });
}

export function useSlAlert(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.alerts.detail(id),
    queryFn: () => slAlertsService.getById(id),
    enabled: !!id,
  });
}

export function useSlAlertStats(organizationId?: string) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.alerts.stats(orgId),
    queryFn: () => slAlertsService.getStats(orgId),
    staleTime: 30 * 1000,
  });
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: AlertAcknowledgeRequest }) =>
      slAlertsService.acknowledge(id, data),
    onSuccess: (_, { id }) => {
      // Invalidate all alert queries
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.alerts.all });
      // Invalidate dashboard
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.dashboard.all });
      // Invalidate patient summaries (alert counts change)
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.all });

      toast.success('Alert acknowledged');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to acknowledge alert');
    },
  });
}

export function useResolveAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AlertResolveRequest }) =>
      slAlertsService.resolve(id, data),
    onSuccess: (_, { id }) => {
      // Invalidate all alert queries
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.alerts.all });
      // Invalidate dashboard
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.dashboard.all });
      // Invalidate patient summaries (alert counts change)
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.all });

      toast.success('Alert resolved');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to resolve alert');
    },
  });
}
