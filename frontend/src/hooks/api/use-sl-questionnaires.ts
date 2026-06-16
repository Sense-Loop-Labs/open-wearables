/**
 * React Query hooks for Sense Loop questionnaire templates
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { slQuestionnairesService } from '@/lib/api/services/sense-loop.service';
import type {
  QuestionCreate,
  QuestionnaireCreate,
  QuestionnaireQueryParams,
  QuestionnaireUpdate,
  QuestionUpdate,
} from '@/lib/api/types/sense-loop';
import { queryKeys } from '@/lib/query/keys';

// ============================================================================
// Questionnaire Templates
// ============================================================================

export function useQuestionnaires(params?: QuestionnaireQueryParams) {
  return useQuery({
    queryKey: queryKeys.sl.questionnaires.list(params),
    queryFn: () => slQuestionnairesService.getAll(params),
    staleTime: 60 * 1000,
  });
}

export function useQuestionnaire(id: string) {
  return useQuery({
    queryKey: queryKeys.sl.questionnaires.detail(id),
    queryFn: () => slQuestionnairesService.getById(id),
    enabled: !!id,
  });
}

export function useCreateQuestionnaire() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: QuestionnaireCreate) =>
      slQuestionnairesService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.lists(),
      });
      toast.success('Questionnaire created');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create questionnaire');
    },
  });
}

export function useUpdateQuestionnaire() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: QuestionnaireUpdate }) =>
      slQuestionnairesService.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(id),
      });
      toast.success('Questionnaire updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update questionnaire');
    },
  });
}

export function useActivateQuestionnaire() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => slQuestionnairesService.activate(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(id),
      });
      toast.success('Questionnaire activated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to activate questionnaire');
    },
  });
}

export function useRetireQuestionnaire() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => slQuestionnairesService.retire(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(id),
      });
      toast.success('Questionnaire retired');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to retire questionnaire');
    },
  });
}

export function useDuplicateQuestionnaire() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      params,
    }: {
      id: string;
      params?: { to_organization_id?: string; new_title?: string; new_code?: string };
    }) => slQuestionnairesService.duplicate(id, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.lists(),
      });
      toast.success('Questionnaire duplicated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to duplicate questionnaire');
    },
  });
}

// ============================================================================
// Questions
// ============================================================================

export function useAddQuestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      questionnaireId,
      data,
    }: {
      questionnaireId: string;
      data: QuestionCreate;
    }) => slQuestionnairesService.addQuestion(questionnaireId, data),
    onSuccess: (_, { questionnaireId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(questionnaireId),
      });
      toast.success('Question added');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to add question');
    },
  });
}

export function useUpdateQuestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      questionnaireId,
      questionId,
      data,
    }: {
      questionnaireId: string;
      questionId: string;
      data: QuestionUpdate;
    }) => slQuestionnairesService.updateQuestion(questionnaireId, questionId, data),
    onSuccess: (_, { questionnaireId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(questionnaireId),
      });
      toast.success('Question updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update question');
    },
  });
}

export function useDeleteQuestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      questionnaireId,
      questionId,
    }: {
      questionnaireId: string;
      questionId: string;
    }) => slQuestionnairesService.deleteQuestion(questionnaireId, questionId),
    onSuccess: (_, { questionnaireId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(questionnaireId),
      });
      toast.success('Question deleted');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to delete question');
    },
  });
}

export function useReorderQuestions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      questionnaireId,
      questions,
    }: {
      questionnaireId: string;
      questions: Array<{ question_id: string; order: number }>;
    }) => slQuestionnairesService.reorderQuestions(questionnaireId, questions),
    onSuccess: (_, { questionnaireId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sl.questionnaires.detail(questionnaireId),
      });
      toast.success('Questions reordered');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reorder questions');
    },
  });
}

// ============================================================================
// Patient Questionnaire Assignment
// ============================================================================

export function usePatientQuestionnaires(patientId: string, status?: string) {
  return useQuery({
    queryKey: ['sl', 'patientQuestionnaires', patientId, status],
    queryFn: () => slQuestionnairesService.getPatientQuestionnaires(patientId, status),
    enabled: !!patientId,
  });
}

export function useAssignQuestionnaire() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      questionnaireId,
    }: {
      patientId: string;
      questionnaireId: string;
    }) => slQuestionnairesService.assignToPatient(patientId, questionnaireId),
    onSuccess: (_, { patientId }) => {
      queryClient.invalidateQueries({
        queryKey: ['sl', 'patientQuestionnaires', patientId],
      });
      toast.success('Questionnaire assigned to patient');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to assign questionnaire');
    },
  });
}

export function useQuestionnaireResponse(responseId: string | undefined) {
  return useQuery({
    queryKey: ['sl', 'questionnaireResponse', responseId],
    queryFn: () => slQuestionnairesService.getResponseDetail(responseId!),
    enabled: !!responseId,
  });
}

// ============================================================================
// Patient Questionnaire Copies
// ============================================================================

export function usePatientQuestionnaireCopies(patientId: string) {
  return useQuery({
    queryKey: ['sl', 'patientQuestionnaireCopies', patientId],
    queryFn: () => slQuestionnairesService.getPatientQuestionnaireCopies(patientId),
    enabled: !!patientId,
  });
}

export function usePatientQuestionnaireCopy(patientId: string, questionnaireId: string) {
  return useQuery({
    queryKey: ['sl', 'patientQuestionnaireCopy', patientId, questionnaireId],
    queryFn: () => slQuestionnairesService.getPatientQuestionnaireCopy(patientId, questionnaireId),
    enabled: !!patientId && !!questionnaireId,
  });
}

export function useCopyQuestionnaireForPatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      templateId,
    }: {
      patientId: string;
      templateId: string;
    }) => slQuestionnairesService.copyQuestionnaireForPatient(patientId, templateId),
    onSuccess: (_, { patientId }) => {
      queryClient.invalidateQueries({
        queryKey: ['sl', 'patientQuestionnaireCopies', patientId],
      });
      queryClient.invalidateQueries({
        queryKey: ['sl', 'patientQuestionnaires', patientId],
      });
      toast.success('Questionnaire copied for patient');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to copy questionnaire');
    },
  });
}

export function useSendQuestionnaireToPatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      patientId,
      questionnaireId,
    }: {
      patientId: string;
      questionnaireId: string;
    }) => slQuestionnairesService.generateResponseForPatientQuestionnaire(patientId, questionnaireId),
    onSuccess: (_, { patientId }) => {
      queryClient.invalidateQueries({
        queryKey: ['sl', 'patientQuestionnaireCopies', patientId],
      });
      queryClient.invalidateQueries({
        queryKey: ['sl', 'patientQuestionnaires', patientId],
      });
      toast.success('Questionnaire sent to patient');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to send questionnaire');
    },
  });
}
