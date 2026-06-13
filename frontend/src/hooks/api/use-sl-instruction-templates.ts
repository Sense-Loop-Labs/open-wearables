/**
 * React Query hooks for Sense Loop instruction templates
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import {
  slActivityTemplatesService,
  slInstructionTemplatesService,
  slPatientPlansService,
} from '@/lib/api/services/sense-loop.service';
import type {
  ActivityTemplateCreate,
  ActivityTemplateQueryParams,
  ActivityTemplateUpdate,
  InstructionTemplateCreate,
  InstructionTemplateQueryParams,
  InstructionTemplateUpdate,
  PatientPlanAssign,
  PatientPlanUpdate,
} from '@/lib/api/types/sense-loop';
import { queryKeys } from '@/lib/query/keys';

// ============================================================================
// Activity Templates
// ============================================================================

export function useActivityTemplates(params?: ActivityTemplateQueryParams) {
  return useQuery({
    queryKey: queryKeys.sl.activityTemplates.list(params),
    queryFn: () => slActivityTemplatesService.getAll(params),
    staleTime: 60 * 1000,
  });
}

export function useActivityTemplate(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.activityTemplates.detail(id),
    queryFn: () => slActivityTemplatesService.getById(id),
    enabled: !!id,
  });
}

export function useCreateActivityTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ActivityTemplateCreate) =>
      slActivityTemplatesService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.lists(),
      });
      toast.success('Activity template created');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create activity template');
    },
  });
}

export function useUpdateActivityTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ActivityTemplateUpdate }) =>
      slActivityTemplatesService.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.detail(id),
      });
      toast.success('Activity template updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update activity template');
    },
  });
}

export function useActivateActivityTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => slActivityTemplatesService.activate(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.detail(id),
      });
      toast.success('Activity template activated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to activate activity template');
    },
  });
}

export function useRetireActivityTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => slActivityTemplatesService.retire(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.activityTemplates.detail(id),
      });
      toast.success('Activity template retired');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to retire activity template');
    },
  });
}

// ============================================================================
// Instruction Templates
// ============================================================================

export function useInstructionTemplates(params?: InstructionTemplateQueryParams) {
  return useQuery({
    queryKey: queryKeys.sl.instructionTemplates.list(params),
    queryFn: () => slInstructionTemplatesService.getAll(params),
    staleTime: 60 * 1000,
  });
}

export function useInstructionTemplate(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.instructionTemplates.detail(id),
    queryFn: () => slInstructionTemplatesService.getById(id),
    enabled: !!id,
  });
}

export function useInstructionTemplatePreview(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.instructionTemplates.preview(id),
    queryFn: () => slInstructionTemplatesService.getPreview(id),
    enabled: !!id,
  });
}

export function useCreateInstructionTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: InstructionTemplateCreate) =>
      slInstructionTemplatesService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.lists(),
      });
      toast.success('Instruction template created');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create instruction template');
    },
  });
}

export function useUpdateInstructionTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: InstructionTemplateUpdate }) =>
      slInstructionTemplatesService.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.detail(id),
      });
      toast.success('Instruction template updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update instruction template');
    },
  });
}

export function useActivateInstructionTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => slInstructionTemplatesService.activate(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.detail(id),
      });
      toast.success('Instruction template activated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to activate instruction template');
    },
  });
}

export function useRetireInstructionTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => slInstructionTemplatesService.retire(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.detail(id),
      });
      toast.success('Instruction template retired');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to retire instruction template');
    },
  });
}

export function useDuplicateInstructionTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      params,
    }: {
      id: string;
      params?: { to_organization_id?: string; new_title?: string };
    }) => slInstructionTemplatesService.duplicate(id, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.instructionTemplates.lists(),
      });
      toast.success('Instruction template duplicated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to duplicate instruction template');
    },
  });
}

// ============================================================================
// Patient Instruction Plans
// ============================================================================

export function usePatientPlans(patientId: string, status?: string) {
  return useQuery({
    queryKey: queryKeys.sl.patientPlans.list(patientId, status),
    queryFn: () => slPatientPlansService.getAll(patientId, status),
    enabled: !!patientId,
    staleTime: 30 * 1000,
  });
}

export function usePatientPlan(patientId: string, planId: string) {
  return useQuery({
    queryKey: queryKeys.sl.patientPlans.detail(patientId, planId),
    queryFn: () => slPatientPlansService.getById(patientId, planId),
    enabled: !!patientId && !!planId,
  });
}

export function usePatientPlanContent(patientId: string, planId: string) {
  return useQuery({
    queryKey: queryKeys.sl.patientPlans.content(patientId, planId),
    queryFn: () => slPatientPlansService.getContent(patientId, planId),
    enabled: !!patientId && !!planId,
  });
}

export function useAssignPatientPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      data,
    }: {
      patientId: string;
      data: PatientPlanAssign;
    }) => slPatientPlansService.assign(patientId, data),
    onSuccess: (_, { patientId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.list(patientId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patients.detail(patientId),
      });
      toast.success('Instruction plan assigned to patient');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to assign instruction plan');
    },
  });
}

export function useUpdatePatientPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      planId,
      data,
    }: {
      patientId: string;
      planId: string;
      data: PatientPlanUpdate;
    }) => slPatientPlansService.update(patientId, planId, data),
    onSuccess: (_, { patientId, planId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.list(patientId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.detail(patientId, planId),
      });
      toast.success('Instruction plan updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update instruction plan');
    },
  });
}

export function useCompletePatientPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ patientId, planId }: { patientId: string; planId: string }) =>
      slPatientPlansService.complete(patientId, planId),
    onSuccess: (_, { patientId, planId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.list(patientId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.detail(patientId, planId),
      });
      toast.success('Instruction plan completed');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to complete instruction plan');
    },
  });
}

export function useCancelPatientPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      planId,
      cancelPendingTasks = true,
    }: {
      patientId: string;
      planId: string;
      cancelPendingTasks?: boolean;
    }) => slPatientPlansService.cancel(patientId, planId, cancelPendingTasks),
    onSuccess: (_, { patientId, planId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.list(patientId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patientPlans.detail(patientId, planId),
      });
      toast.success('Instruction plan cancelled');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to cancel instruction plan');
    },
  });
}
