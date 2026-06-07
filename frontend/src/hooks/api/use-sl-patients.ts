/**
 * Sense Loop Patients Hooks
 * React Query hooks for patient management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slPatientsService } from '@/lib/api/services/sense-loop.service';
import type {
  Patient,
  PatientCreate,
  PatientQueryParams,
  PatientUpdate,
} from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { queryKeys } from '@/lib/query/keys';

export function useSlPatients(params?: PatientQueryParams) {
  const orgId = params?.organization_id || getSlCurrentOrgId() || undefined;
  const queryParams = { ...params, organization_id: orgId };

  return useQuery({
    queryKey: queryKeys.sl.patients.list(queryParams),
    queryFn: () => slPatientsService.getAll(queryParams),
    placeholderData: (previousData) => previousData,
    staleTime: 60 * 1000, // 1 minute
  });
}

export function useSlPatient(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.patients.detail(id),
    queryFn: () => slPatientsService.getById(id),
    enabled: !!id,
  });
}

export function useCreateSlPatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PatientCreate) => slPatientsService.create(data),
    onSuccess: (newPatient) => {
      // Invalidate patient lists
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.lists() });
      // Invalidate dashboard (patient counts may have changed)
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.dashboard.all });

      toast.success(`Patient ${newPatient.full_name} created successfully`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create patient');
    },
  });
}

export function useUpdateSlPatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PatientUpdate }) =>
      slPatientsService.update(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.sl.patients.detail(id) });

      // Snapshot previous value
      const previousPatient = queryClient.getQueryData<Patient>(
        queryKeys.sl.patients.detail(id)
      );

      // Optimistically update
      if (previousPatient) {
        queryClient.setQueryData<Patient>(queryKeys.sl.patients.detail(id), {
          ...previousPatient,
          ...data,
          updated_at: new Date().toISOString(),
        });
      }

      return { previousPatient };
    },
    onSuccess: (updatedPatient, { id }) => {
      queryClient.setQueryData(queryKeys.sl.patients.detail(id), updatedPatient);
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.lists() });

      toast.success('Patient updated successfully');
    },
    onError: (error: Error, { id }, context) => {
      // Rollback on error
      if (context?.previousPatient) {
        queryClient.setQueryData(queryKeys.sl.patients.detail(id), context.previousPatient);
      }
      toast.error(error.message || 'Failed to update patient');
    },
  });
}

export function useGenerateActivationCode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (patientId: string) => slPatientsService.generateActivationCode(patientId),
    onSuccess: (result, patientId) => {
      // Invalidate patient detail to refresh activation code
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.detail(patientId) });

      toast.success(`Activation code generated: ${result.activation_code}`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to generate activation code');
    },
  });
}

export function useDischargePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (patientId: string) => slPatientsService.discharge(patientId),
    onSuccess: (patient) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.lists() });
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.patients.detail(patient.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.dashboard.all });

      toast.success(`Patient ${patient.full_name} has been discharged`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to discharge patient');
    },
  });
}
