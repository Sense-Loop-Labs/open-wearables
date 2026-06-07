/**
 * Sense Loop Clinicians Hooks
 * React Query hooks for clinician management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slCliniciansService } from '@/lib/api/services/sense-loop.service';
import type { InviteClinicianRequest } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { queryKeys } from '@/lib/query/keys';

export function useSlClinicians(organizationId?: string) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.clinicians.list(orgId),
    queryFn: () => slCliniciansService.getAll(orgId),
    staleTime: 60 * 1000, // 1 minute
  });
}

export function useSlClinician(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.clinicians.detail(id),
    queryFn: () => slCliniciansService.getById(id),
    enabled: !!id,
  });
}

export function useSlRoles() {
  return useQuery({
    queryKey: queryKeys.sl.clinicians.roles(),
    queryFn: () => slCliniciansService.getRoles(),
    staleTime: 10 * 60 * 1000, // 10 minutes - roles don't change often
  });
}

export function useInviteClinician() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      organizationId,
      data,
    }: {
      organizationId: string;
      data: InviteClinicianRequest;
    }) => slCliniciansService.invite(organizationId, data),
    onSuccess: (invite) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.lists() });

      toast.success(`Invitation sent to ${invite.email}`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to send invitation');
    },
  });
}

export function useDeactivateClinician() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (clinicianId: string) => slCliniciansService.deactivate(clinicianId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.all });

      toast.success('Clinician deactivated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to deactivate clinician');
    },
  });
}
