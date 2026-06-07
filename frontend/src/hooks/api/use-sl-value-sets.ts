/**
 * Sense Loop Value Sets Hooks
 * React Query hooks for value set management
 */

import { useQuery } from '@tanstack/react-query';

import { slValueSetsService } from '@/lib/api/services/sense-loop.service';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';

export function useSlValueSetItems(code: string, options?: { enabled?: boolean }) {
  const orgId = getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: ['sl', 'value-sets', code, 'items', orgId],
    queryFn: () => slValueSetsService.getItems(code, orgId),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000, // 5 minutes - value sets rarely change
  });
}

export function useSurgeryTypes() {
  return useSlValueSetItems('surgery-types');
}
