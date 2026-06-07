/**
 * Sense Loop Dashboard Hooks
 * React Query hooks for dashboard data
 */

import { useQuery } from '@tanstack/react-query';

import { slDashboardService } from '@/lib/api/services/sense-loop.service';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { queryKeys } from '@/lib/query/keys';

export function useSlDashboardOverview(organizationId?: string) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.dashboard.overview(orgId),
    queryFn: () => slDashboardService.getOverview(orgId),
    staleTime: 30 * 1000, // 30 seconds - dashboard should refresh frequently
  });
}

export function useSlCriticalPatients(organizationId?: string, limit = 10) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.dashboard.criticalPatients(orgId),
    queryFn: () => slDashboardService.getCriticalPatients(orgId, limit),
    staleTime: 30 * 1000,
  });
}

export function useSlRecentAlerts(organizationId?: string, limit = 10) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.dashboard.recentAlerts(orgId),
    queryFn: () => slDashboardService.getRecentAlerts(orgId, limit),
    staleTime: 30 * 1000,
  });
}

export function useSlAlertsByDay(organizationId?: string, days = 7) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.dashboard.alertsByDay(orgId, days),
    queryFn: () => slDashboardService.getAlertsByDay(orgId, days),
    staleTime: 5 * 60 * 1000, // 5 minutes - chart data doesn't need to refresh as often
  });
}
