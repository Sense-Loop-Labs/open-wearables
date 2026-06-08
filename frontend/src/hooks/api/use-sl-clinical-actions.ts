/**
 * Sense Loop Clinical Actions Hooks
 * React Query hooks for clinical action management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slClinicalActionsService } from '@/lib/api/services/sense-loop.service';
import type { ClinicalActionCreate } from '@/lib/api/types/sense-loop';
import { queryKeys } from '@/lib/query/keys';

export function useSlClinicalActions(
  patientId: string,
  params?: { page?: number; page_size?: number }
) {
  return useQuery({
    queryKey: queryKeys.sl.clinicalActions.list(patientId, params),
    queryFn: () => slClinicalActionsService.getAll(patientId, params),
    enabled: !!patientId,
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useCreateSlClinicalAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      data,
    }: {
      patientId: string;
      data: ClinicalActionCreate;
    }) => slClinicalActionsService.create(patientId, data),
    onSuccess: (newAction, { patientId }) => {
      // Invalidate clinical actions list for this patient
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.clinicalActions.lists(),
      });
      // Invalidate patient lists to update "Last Action" column
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.patients.lists(),
      });

      toast.success(`${newAction.category_display} logged successfully`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to log clinical action');
    },
  });
}
