/**
 * Sense Loop Clinicians Hooks
 * React Query hooks for clinician management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slCliniciansService } from '@/lib/api/services/sense-loop.service';
import type { ClinicianUpdate, InviteClinicianRequest } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { ApiError } from '@/lib/errors/api-error';
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

export function useSlRoles(organizationId?: string) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.clinicians.roles(orgId),
    queryFn: () => slCliniciansService.getRoles(orgId!),
    enabled: !!orgId,
    staleTime: 10 * 60 * 1000, // 10 minutes - roles don't change often
  });
}

export function useSlPendingInvites(organizationId?: string) {
  const orgId = organizationId || getSlCurrentOrgId() || undefined;

  return useQuery({
    queryKey: queryKeys.sl.clinicians.pendingInvites(orgId),
    queryFn: () => slCliniciansService.getPendingInvites(orgId!),
    enabled: !!orgId,
    staleTime: 30 * 1000, // 30 seconds - invites can change frequently
  });
}

/**
 * Parse FastAPI/Pydantic validation errors into field-level errors
 */
export function parseValidationErrors(
  error: unknown
): Record<string, string> | null {
  if (!(error instanceof ApiError)) return null;

  const details = error.details as Record<string, unknown> | undefined;
  if (!details) return null;

  // FastAPI validation errors are stored in validationErrors array
  const validationErrors = details.validationErrors as Array<{
    loc: (string | number)[];
    msg: string;
    type: string;
  }> | undefined;

  if (Array.isArray(validationErrors)) {
    const fieldErrors: Record<string, string> = {};
    for (const err of validationErrors) {
      // loc is like ["body", "field_name"] or ["body", "field_name", 0]
      const loc = err.loc;
      // Get the last string element as the field name
      const fieldName = [...loc].reverse().find((l) => typeof l === 'string');
      if (fieldName && typeof fieldName === 'string' && fieldName !== 'body') {
        fieldErrors[fieldName] = err.msg;
      }
    }
    return Object.keys(fieldErrors).length > 0 ? fieldErrors : null;
  }

  // Check if details is already a field -> message map
  if (details && typeof details === 'object' && !('validationErrors' in details)) {
    return details as Record<string, string>;
  }

  return null;
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
      // Invalidate both clinicians list and pending invites
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.lists() });
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.all });

      toast.success(`Invitation sent to ${invite.email}`);
    },
    // Let component handle field-level errors via the error state
    throwOnError: false,
  });
}

export function useUpdateClinician() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      clinicianId,
      data,
      organizationId,
    }: {
      clinicianId: string;
      data: ClinicianUpdate;
      organizationId: string;
    }) => slCliniciansService.update(clinicianId, data, organizationId),
    onSuccess: (clinician) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.all });
      toast.success(`${clinician.first_name} ${clinician.last_name} updated`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update clinician');
    },
  });
}

export function useDeactivateClinician() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      clinicianId,
      organizationId,
    }: {
      clinicianId: string;
      organizationId: string;
    }) => slCliniciansService.deactivate(clinicianId, organizationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.all });

      toast.success('Clinician deactivated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to deactivate clinician');
    },
  });
}

export function useResendInvite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (inviteId: string) => slCliniciansService.resendInvite(inviteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.all });
      toast.success('Invitation resent');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to resend invitation');
    },
  });
}

export function useRevokeInvite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (inviteId: string) => slCliniciansService.revokeInvite(inviteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.clinicians.all });
      toast.success('Invitation revoked');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to revoke invitation');
    },
  });
}
