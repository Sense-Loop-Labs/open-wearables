/**
 * Patient Questionnaire Editor Page
 * Allows editing of a patient-specific questionnaire copy
 */

import { useState, useEffect } from 'react';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ArrowLeft,
  Plus,
  GripVertical,
  Trash2,
  AlertTriangle,
  Info,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import { SlInput } from '@/components/sl/ui/sl-input';
import { SlTextarea } from '@/components/sl/ui/sl-textarea';
import { SlLabel } from '@/components/sl/ui/sl-label';
import { SlBadge } from '@/components/sl/ui/sl-badge';
import {
  SlSelect,
  SlSelectContent,
  SlSelectItem,
  SlSelectTrigger,
  SlSelectValue,
} from '@/components/sl/ui/sl-select';
import {
  SlDialog,
  SlDialogContent,
  SlDialogDescription,
  SlDialogFooter,
  SlDialogHeader,
  SlDialogTitle,
} from '@/components/sl/ui/sl-dialog';

import {
  useQuestionnaire,
  useAddQuestion,
  useUpdateQuestion,
  useDeleteQuestion,
  useReorderQuestions,
} from '@/hooks/api/use-sl-questionnaires';
import { useSlPatient } from '@/hooks/api/use-sl-patients';
import type { QuestionnaireQuestion, QuestionOption, QuestionAlertConfig } from '@/lib/api/types/sense-loop';

export const Route = createFileRoute(
  '/sl/_sl-authenticated/patients/$patientId/questionnaires/$questionnaireId/edit'
)({
  component: PatientQuestionnaireEditorPage,
});

const QUESTION_TYPES = [
  { value: 'boolean', label: 'Yes/No (Boolean)' },
  { value: 'single_choice', label: 'Single Choice' },
  { value: 'multi_choice', label: 'Multiple Choice' },
  { value: 'scale', label: 'Scale (0-10)' },
  { value: 'number', label: 'Number Input' },
  { value: 'text', label: 'Text Input' },
];

function PatientQuestionnaireEditorPage() {
  const { patientId, questionnaireId } = Route.useParams();
  const navigate = useNavigate();

  const { data: patient, isLoading: patientLoading } = useSlPatient(patientId);
  const { data: questionnaire, isLoading: questionnaireLoading, error } = useQuestionnaire(questionnaireId);
  const reorderMutation = useReorderQuestions();

  const [isAddQuestionDialogOpen, setIsAddQuestionDialogOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<QuestionnaireQuestion | null>(null);

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id && questionnaire) {
      const oldIndex = questionnaire.questions.findIndex((q) => q.id === active.id);
      const newIndex = questionnaire.questions.findIndex((q) => q.id === over.id);

      if (oldIndex !== -1 && newIndex !== -1) {
        const reorderedQuestions = arrayMove(questionnaire.questions, oldIndex, newIndex);
        const updates = reorderedQuestions.map((q, idx) => ({
          question_id: q.id,
          order: idx,
        }));

        reorderMutation.mutate({
          questionnaireId,
          questions: updates,
        });
      }
    }
  };

  const isLoading = patientLoading || questionnaireLoading;

  if (isLoading) {
    return <EditorSkeleton />;
  }

  if (error || !questionnaire || !patient) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Failed to load questionnaire</p>
        <Button
          variant="outline"
          onClick={() => navigate({ to: '/sl/patients/$patientId', params: { patientId } })}
          className="mt-4"
        >
          Back to Patient
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/sl/patients/$patientId"
            params={{ patientId }}
            className="p-2 hover:bg-[var(--sl-bg-hover)] rounded-lg transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-[var(--sl-text-secondary)]" />
          </Link>
          <div>
            <div className="flex items-center gap-2 text-sm text-[var(--sl-text-secondary)]">
              <Link to="/sl/patients" className="hover:text-[var(--sl-text-primary)]">
                Patients
              </Link>
              <span>/</span>
              <Link
                to="/sl/patients/$patientId"
                params={{ patientId }}
                className="hover:text-[var(--sl-text-primary)]"
              >
                {patient.full_name}
              </Link>
              <span>/</span>
              <span className="text-[var(--sl-text-primary)]">{questionnaire.title}</span>
            </div>
            <h1 className="text-2xl font-semibold text-[var(--sl-text-primary)] mt-1">
              Edit Questionnaire
            </h1>
          </div>
        </div>
        <Button onClick={() => setIsAddQuestionDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Question
        </Button>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3">
        <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-medium">Patient-Specific Questionnaire</p>
          <p className="mt-1">
            This is a customized copy for {patient.full_name}. Changes here will not affect the
            original template.
          </p>
        </div>
      </div>

      {/* Questionnaire Info */}
      <div className="bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-[var(--sl-text-muted)]">Type:</span>
            <span className="ml-2 text-[var(--sl-text-primary)] capitalize">
              {questionnaire.questionnaire_type.replace('_', ' ')}
            </span>
          </div>
          <div>
            <span className="text-[var(--sl-text-muted)]">Category:</span>
            <span className="ml-2 text-[var(--sl-text-primary)] capitalize">
              {questionnaire.category}
            </span>
          </div>
          <div>
            <span className="text-[var(--sl-text-muted)]">Questions:</span>
            <span className="ml-2 text-[var(--sl-text-primary)]">
              {questionnaire.question_count}
            </span>
          </div>
          <div>
            <span className="text-[var(--sl-text-muted)]">Scoring:</span>
            <span className="ml-2 text-[var(--sl-text-primary)]">
              {questionnaire.has_scoring ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        </div>
      </div>

      {/* Questions List */}
      <div className="space-y-4">
        <h2 className="text-lg font-medium text-[var(--sl-text-primary)]">Questions</h2>

        {questionnaire.questions.length === 0 ? (
          <div className="text-center py-12 bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg">
            <p className="text-[var(--sl-text-muted)]">No questions yet</p>
            <Button onClick={() => setIsAddQuestionDialogOpen(true)} className="mt-4">
              <Plus className="h-4 w-4 mr-2" />
              Add First Question
            </Button>
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={questionnaire.questions.map((q) => q.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-3">
                {questionnaire.questions.map((question, index) => (
                  <SortableQuestionCard
                    key={question.id}
                    question={question}
                    index={index}
                    onEdit={() => setEditingQuestion(question)}
                    questionnaireId={questionnaireId}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>

      {/* Add Question Dialog */}
      <QuestionFormDialog
        open={isAddQuestionDialogOpen}
        onOpenChange={setIsAddQuestionDialogOpen}
        questionnaireId={questionnaireId}
        hasScoring={questionnaire.has_scoring}
      />

      {/* Edit Question Dialog */}
      {editingQuestion && (
        <QuestionFormDialog
          open={!!editingQuestion}
          onOpenChange={(open) => !open && setEditingQuestion(null)}
          questionnaireId={questionnaireId}
          question={editingQuestion}
          hasScoring={questionnaire.has_scoring}
        />
      )}
    </div>
  );
}

function SortableQuestionCard({
  question,
  index,
  onEdit,
  questionnaireId,
}: {
  question: QuestionnaireQuestion;
  index: number;
  onEdit: () => void;
  questionnaireId: string;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: question.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const deleteMutation = useDeleteQuestion();
  const hasAlertConfig = question.alert_config && ((question.alert_config.trigger_values?.length ?? 0) > 0 || question.alert_config.alert_on_any_value);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg p-4 hover:border-[var(--sl-border-hover)] transition-colors"
    >
      <div className="flex items-start gap-3">
        <div
          {...attributes}
          {...listeners}
          className="flex items-center gap-2 text-[var(--sl-text-muted)] cursor-grab active:cursor-grabbing"
        >
          <GripVertical className="h-4 w-4" />
          <span className="text-sm font-medium">{index + 1}</span>
        </div>

        <div className="flex-1">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-[var(--sl-text-primary)]">
                {question.text}
                {question.is_required && <span className="text-red-500 ml-1">*</span>}
              </p>
              {question.help_text && (
                <p className="text-sm text-[var(--sl-text-muted)] mt-1">{question.help_text}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={onEdit}>
                Edit
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50"
                onClick={() => {
                  if (confirm('Are you sure you want to delete this question?')) {
                    deleteMutation.mutate({
                      questionnaireId,
                      questionId: question.id,
                    });
                  }
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-3">
            <SlBadge variant="outline" className="text-xs">
              {QUESTION_TYPES.find((t) => t.value === question.question_type)?.label || question.question_type}
            </SlBadge>
            <SlBadge variant="outline" className="text-xs">
              Code: {question.code}
            </SlBadge>
            {question.options && (
              <SlBadge variant="outline" className="text-xs">
                {question.options.length} options
              </SlBadge>
            )}
            {hasAlertConfig && (
              <SlBadge variant="destructive" className="text-xs">
                <AlertTriangle className="h-3 w-3 mr-1" />
                Alert configured
              </SlBadge>
            )}
          </div>

          {/* Show options for choice questions */}
          {question.options && question.options.length > 0 && (
            <div className="mt-3 space-y-1">
              {question.options.map((option, idx) => {
                const isAlertTrigger = question.alert_config?.trigger_values?.includes(option.value);
                const severity = question.alert_config?.severity_by_value?.[option.value] || question.alert_config?.alert_severity || 'info';
                return (
                  <div
                    key={idx}
                    className="flex items-center gap-2 text-sm text-[var(--sl-text-secondary)]"
                  >
                    <span className="w-4 h-4 rounded border border-[var(--sl-border)] flex-shrink-0" />
                    <span>{option.label}</span>
                    {option.score !== undefined && option.score !== null && (
                      <span className="text-xs text-[var(--sl-text-muted)]">(score: {option.score})</span>
                    )}
                    {isAlertTrigger && (
                      <span className={`flex items-center gap-1 text-xs ${
                        severity === 'critical'
                          ? 'text-red-600'
                          : severity === 'warning'
                          ? 'text-yellow-600'
                          : 'text-blue-600'
                      }`}>
                        <AlertTriangle className="h-3 w-3" />
                        {severity}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function QuestionFormDialog({
  open,
  onOpenChange,
  questionnaireId,
  question,
  hasScoring,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  questionnaireId: string;
  question?: QuestionnaireQuestion;
  hasScoring: boolean;
}) {
  const addMutation = useAddQuestion();
  const updateMutation = useUpdateQuestion();

  const isEditing = !!question;

  const [code, setCode] = useState(question?.code || '');
  const [text, setText] = useState(question?.text || '');
  const [helpText, setHelpText] = useState(question?.help_text || '');
  const [questionType, setQuestionType] = useState<string>(question?.question_type || 'single_choice');
  const [isRequired, setIsRequired] = useState(question?.is_required ?? true);
  const [options, setOptions] = useState<QuestionOption[]>(
    question?.options || [{ value: '', label: '', score: undefined }]
  );
  const [alertConfig, setAlertConfig] = useState<QuestionAlertConfig>(
    question?.alert_config || { trigger_values: [], alert_severity: 'warning', alert_message: '', alert_on_any_value: false }
  );
  const [optionSeverities, setOptionSeverities] = useState<Record<string, 'info' | 'warning' | 'critical'>>(
    question?.alert_config?.severity_by_value || {}
  );
  const [scaleMin, setScaleMin] = useState(question?.validation?.min?.toString() || '0');
  const [scaleMax, setScaleMax] = useState(question?.validation?.max?.toString() || '10');

  const showOptions = ['single_choice', 'multi_choice'].includes(questionType);
  const showScale = questionType === 'scale';

  useEffect(() => {
    if (open) {
      if (question) {
        setCode(question.code || '');
        setText(question.text || '');
        setHelpText(question.help_text || '');
        setQuestionType(question.question_type || 'single_choice');
        setIsRequired(question.is_required ?? true);
        setOptions(question.options || [{ value: '', label: '', score: undefined }]);
        setAlertConfig(question.alert_config || { trigger_values: [], alert_severity: 'warning', alert_message: '', alert_on_any_value: false });
        setOptionSeverities(question.alert_config?.severity_by_value || {});
        setScaleMin(question.validation?.min?.toString() || '0');
        setScaleMax(question.validation?.max?.toString() || '10');
      } else {
        resetForm();
      }
    }
  }, [open, question]);

  const resetForm = () => {
    setCode('');
    setText('');
    setHelpText('');
    setQuestionType('single_choice');
    setIsRequired(true);
    setOptions([{ value: '', label: '', score: undefined }]);
    setAlertConfig({ trigger_values: [], alert_severity: 'warning', alert_message: '', alert_on_any_value: false });
    setOptionSeverities({});
    setScaleMin('0');
    setScaleMax('10');
  };

  const handleClose = () => {
    if (!isEditing) {
      resetForm();
    }
    onOpenChange(false);
  };

  const handleSubmit = () => {
    const questionData = {
      code,
      text,
      help_text: helpText || undefined,
      question_type: questionType,
      is_required: isRequired,
      options: showOptions
        ? options.filter((o) => o.value).map((o, idx) => ({
            value: o.value,
            label: o.label || o.value,
            score: hasScoring ? (o.score ?? idx) : undefined,
          }))
        : undefined,
      validation: showScale
        ? { min: parseFloat(scaleMin), max: parseFloat(scaleMax) }
        : undefined,
      alert_config: ((alertConfig.trigger_values?.length ?? 0) > 0 || alertConfig.alert_on_any_value)
        ? {
            trigger_values: (alertConfig.trigger_values?.length ?? 0) > 0 ? alertConfig.trigger_values : undefined,
            alert_severity: (alertConfig.alert_severity || 'warning') as 'info' | 'warning' | 'critical',
            alert_message: alertConfig.alert_message || undefined,
            severity_by_value: Object.keys(optionSeverities).length > 0 ? optionSeverities : undefined,
            alert_on_any_value: alertConfig.alert_on_any_value || undefined,
          }
        : undefined,
    };

    if (isEditing && question) {
      updateMutation.mutate(
        {
          questionnaireId,
          questionId: question.id,
          data: questionData,
        },
        {
          onSuccess: () => handleClose(),
        }
      );
    } else {
      addMutation.mutate(
        { questionnaireId, data: questionData },
        {
          onSuccess: () => {
            resetForm();
            handleClose();
          },
        }
      );
    }
  };

  const addOption = () => {
    setOptions([...options, { value: '', label: '', score: undefined }]);
  };

  const updateOption = (index: number, field: keyof QuestionOption, value: string | number) => {
    const newOptions = [...options];
    if (field === 'score') {
      newOptions[index] = { ...newOptions[index], [field]: value === '' ? undefined : Number(value) };
    } else {
      newOptions[index] = { ...newOptions[index], [field]: value };
    }
    setOptions(newOptions);
  };

  const updateOptionLabelAndValue = (index: number, newValue: string) => {
    const newOptions = [...options];
    newOptions[index] = { ...newOptions[index], label: newValue, value: newValue };
    setOptions(newOptions);
  };

  const removeOption = (index: number) => {
    setOptions(options.filter((_, i) => i !== index));
  };

  const toggleAlertTrigger = (value: string) => {
    const currentTriggers = alertConfig.trigger_values || [];
    if (currentTriggers.includes(value)) {
      setAlertConfig({ ...alertConfig, trigger_values: currentTriggers.filter((v) => v !== value) });
      const newSeverities = { ...optionSeverities };
      delete newSeverities[value];
      setOptionSeverities(newSeverities);
    } else {
      setAlertConfig({ ...alertConfig, trigger_values: [...currentTriggers, value] });
      setOptionSeverities({ ...optionSeverities, [value]: 'info' });
    }
  };

  const setOptionSeverity = (value: string, severity: 'info' | 'warning' | 'critical') => {
    setOptionSeverities({ ...optionSeverities, [value]: severity });
  };

  return (
    <SlDialog open={open} onOpenChange={handleClose}>
      <SlDialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <SlDialogHeader>
          <SlDialogTitle>{isEditing ? 'Edit Question' : 'Add Question'}</SlDialogTitle>
          <SlDialogDescription>
            {isEditing ? 'Update the question details' : 'Add a new question to this patient\'s questionnaire'}
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-4 py-4">
          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <SlLabel htmlFor="question-code">Question ID</SlLabel>
              <SlInput
                id="question-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="e.g., pain_level"
              />
              <p className="text-xs text-[var(--sl-text-muted)]">
                Internal identifier (lowercase, no spaces)
              </p>
            </div>
            <div className="space-y-2">
              <SlLabel htmlFor="question-type">Type</SlLabel>
              <SlSelect value={questionType} onValueChange={setQuestionType}>
                <SlSelectTrigger>
                  <SlSelectValue />
                </SlSelectTrigger>
                <SlSelectContent>
                  {QUESTION_TYPES.map((type) => (
                    <SlSelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SlSelectItem>
                  ))}
                </SlSelectContent>
              </SlSelect>
            </div>
          </div>

          <div className="space-y-2">
            <SlLabel htmlFor="question-text">Question Text</SlLabel>
            <SlTextarea
              id="question-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="e.g., How would you rate your pain today?"
              rows={2}
            />
          </div>

          <div className="space-y-2">
            <SlLabel htmlFor="question-help">Help Text (Optional)</SlLabel>
            <SlInput
              id="question-help"
              value={helpText}
              onChange={(e) => setHelpText(e.target.value)}
              placeholder="Additional instructions for the patient"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is-required"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="is-required" className="text-sm text-[var(--sl-text-primary)]">
              Required question
            </label>
          </div>

          {/* Scale Options */}
          {showScale && (
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-[var(--sl-text-primary)] mb-3">Scale Range</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <SlLabel htmlFor="scale-min">Minimum</SlLabel>
                  <SlInput
                    id="scale-min"
                    type="number"
                    value={scaleMin}
                    onChange={(e) => setScaleMin(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <SlLabel htmlFor="scale-max">Maximum</SlLabel>
                  <SlInput
                    id="scale-max"
                    type="number"
                    value={scaleMax}
                    onChange={(e) => setScaleMax(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Boolean Alert Configuration */}
          {questionType === 'boolean' && (
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-[var(--sl-text-primary)] mb-3">
                <AlertTriangle className="h-4 w-4 inline mr-1 text-orange-500" />
                Alert Configuration
              </h4>
              <p className="text-xs text-[var(--sl-text-muted)] mb-3">
                Configure which answer should trigger an alert
              </p>
              <div className="space-y-3">
                {/* Yes option */}
                <div className="flex items-center gap-3">
                  <span className="w-12 text-sm font-medium text-[var(--sl-text-primary)]">Yes</span>
                  <button
                    type="button"
                    onClick={() => toggleAlertTrigger('true')}
                    className={`p-2 rounded-md transition-colors ${
                      alertConfig.trigger_values?.includes('true')
                        ? (optionSeverities['true'] || 'info') === 'critical'
                          ? 'bg-red-100 text-red-600'
                          : (optionSeverities['true'] || 'info') === 'warning'
                          ? 'bg-yellow-100 text-yellow-600'
                          : 'bg-blue-100 text-blue-600'
                        : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                    }`}
                    title={alertConfig.trigger_values?.includes('true') ? 'Alert enabled' : 'Click to enable alert'}
                  >
                    <AlertTriangle className="h-4 w-4" />
                  </button>
                  {alertConfig.trigger_values?.includes('true') && (
                    <SlSelect
                      value={optionSeverities['true'] || 'info'}
                      onValueChange={(val) => setOptionSeverity('true', val as 'info' | 'warning' | 'critical')}
                    >
                      <SlSelectTrigger className="w-28">
                        <SlSelectValue />
                      </SlSelectTrigger>
                      <SlSelectContent>
                        <SlSelectItem value="info">Info</SlSelectItem>
                        <SlSelectItem value="warning">Warning</SlSelectItem>
                        <SlSelectItem value="critical">Critical</SlSelectItem>
                      </SlSelectContent>
                    </SlSelect>
                  )}
                </div>
                {/* No option */}
                <div className="flex items-center gap-3">
                  <span className="w-12 text-sm font-medium text-[var(--sl-text-primary)]">No</span>
                  <button
                    type="button"
                    onClick={() => toggleAlertTrigger('false')}
                    className={`p-2 rounded-md transition-colors ${
                      alertConfig.trigger_values?.includes('false')
                        ? (optionSeverities['false'] || 'info') === 'critical'
                          ? 'bg-red-100 text-red-600'
                          : (optionSeverities['false'] || 'info') === 'warning'
                          ? 'bg-yellow-100 text-yellow-600'
                          : 'bg-blue-100 text-blue-600'
                        : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                    }`}
                    title={alertConfig.trigger_values?.includes('false') ? 'Alert enabled' : 'Click to enable alert'}
                  >
                    <AlertTriangle className="h-4 w-4" />
                  </button>
                  {alertConfig.trigger_values?.includes('false') && (
                    <SlSelect
                      value={optionSeverities['false'] || 'info'}
                      onValueChange={(val) => setOptionSeverity('false', val as 'info' | 'warning' | 'critical')}
                    >
                      <SlSelectTrigger className="w-28">
                        <SlSelectValue />
                      </SlSelectTrigger>
                      <SlSelectContent>
                        <SlSelectItem value="info">Info</SlSelectItem>
                        <SlSelectItem value="warning">Warning</SlSelectItem>
                        <SlSelectItem value="critical">Critical</SlSelectItem>
                      </SlSelectContent>
                    </SlSelect>
                  )}
                </div>
              </div>
              {alertConfig.trigger_values && alertConfig.trigger_values.length > 0 && (
                <div className="mt-4 space-y-2">
                  <SlLabel htmlFor="boolean-alert-message">Alert Message</SlLabel>
                  <SlTextarea
                    id="boolean-alert-message"
                    value={alertConfig.alert_message || ''}
                    onChange={(e) => setAlertConfig({ ...alertConfig, alert_message: e.target.value })}
                    placeholder="e.g., Patient answered Yes - follow up required"
                    rows={2}
                  />
                </div>
              )}
            </div>
          )}

          {/* Text/Number Alert Configuration */}
          {(questionType === 'text' || questionType === 'number') && (
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-[var(--sl-text-primary)] mb-3">
                <AlertTriangle className="h-4 w-4 inline mr-1 text-orange-500" />
                Alert Configuration
              </h4>
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="alert-on-any-value"
                  checked={alertConfig.alert_on_any_value || false}
                  onChange={(e) => setAlertConfig({ ...alertConfig, alert_on_any_value: e.target.checked })}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="alert-on-any-value" className="text-sm text-[var(--sl-text-primary)]">
                  Flag if answered
                </label>
                {alertConfig.alert_on_any_value && (
                  <SlSelect
                    value={alertConfig.alert_severity || 'warning'}
                    onValueChange={(val) => setAlertConfig({ ...alertConfig, alert_severity: val as 'info' | 'warning' | 'critical' })}
                  >
                    <SlSelectTrigger className="w-28">
                      <SlSelectValue />
                    </SlSelectTrigger>
                    <SlSelectContent>
                      <SlSelectItem value="warning">Warning</SlSelectItem>
                      <SlSelectItem value="critical">Critical</SlSelectItem>
                    </SlSelectContent>
                  </SlSelect>
                )}
              </div>
              <p className="text-xs text-[var(--sl-text-muted)] mt-2">
                When enabled, any response will appear in the symptom concerns on the dashboard
              </p>
            </div>
          )}

          {/* Choice Options */}
          {showOptions && (
            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-[var(--sl-text-primary)]">Answer Options</h4>
                <Button variant="outline" size="sm" onClick={addOption}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Option
                </Button>
              </div>

              <div className="space-y-2">
                {options.map((option, index) => {
                  const optionKey = option.value || option.label;
                  const isAlertTrigger = alertConfig.trigger_values?.includes(optionKey);
                  const severity = optionSeverities[optionKey] || 'info';
                  return (
                    <div key={index} className="flex items-center gap-2">
                      <SlInput
                        value={option.label || option.value}
                        onChange={(e) => updateOptionLabelAndValue(index, e.target.value)}
                        placeholder="Option text (e.g., Excellent)"
                        className="flex-1"
                      />
                      {hasScoring && (
                        <SlInput
                          type="number"
                          value={option.score?.toString() || ''}
                          onChange={(e) => updateOption(index, 'score', e.target.value)}
                          placeholder="Score"
                          className="w-20"
                        />
                      )}
                      <button
                        type="button"
                        onClick={() => optionKey && toggleAlertTrigger(optionKey)}
                        disabled={!optionKey}
                        className={`p-2 rounded-md transition-colors ${
                          isAlertTrigger
                            ? severity === 'critical'
                              ? 'bg-red-100 text-red-600'
                              : severity === 'warning'
                              ? 'bg-yellow-100 text-yellow-600'
                              : 'bg-blue-100 text-blue-600'
                            : 'bg-gray-100 text-gray-400 hover:bg-gray-200 disabled:opacity-50'
                        }`}
                        title={isAlertTrigger ? `Alert: ${severity}` : 'Click to enable alert'}
                      >
                        <AlertTriangle className="h-4 w-4" />
                      </button>
                      {isAlertTrigger && (
                        <SlSelect
                          value={severity}
                          onValueChange={(val) => setOptionSeverity(optionKey, val as 'info' | 'warning' | 'critical')}
                        >
                          <SlSelectTrigger className="w-24">
                            <SlSelectValue />
                          </SlSelectTrigger>
                          <SlSelectContent>
                            <SlSelectItem value="info">Info</SlSelectItem>
                            <SlSelectItem value="warning">Warning</SlSelectItem>
                            <SlSelectItem value="critical">Critical</SlSelectItem>
                          </SlSelectContent>
                        </SlSelect>
                      )}
                      {options.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500"
                          onClick={() => removeOption(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Alert Message */}
          {alertConfig.trigger_values && alertConfig.trigger_values.length > 0 && questionType !== 'boolean' && (
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-[var(--sl-text-primary)] mb-3">
                <AlertTriangle className="h-4 w-4 inline mr-1 text-orange-500" />
                Alert Configuration
              </h4>

              <div className="space-y-3">
                <div className="space-y-2">
                  <SlLabel htmlFor="alert-message">Alert Message</SlLabel>
                  <SlTextarea
                    id="alert-message"
                    value={alertConfig.alert_message || ''}
                    onChange={(e) => setAlertConfig({ ...alertConfig, alert_message: e.target.value })}
                    placeholder="e.g., Patient reported concerning symptoms - requires attention"
                    rows={2}
                  />
                </div>

                <div className="text-xs text-[var(--sl-text-muted)] space-y-1">
                  <p className="font-medium">Triggers configured:</p>
                  {alertConfig.trigger_values.map((value) => {
                    const valueSeverity = optionSeverities[value] || 'info';
                    return (
                      <div key={value} className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          valueSeverity === 'critical'
                            ? 'bg-red-100 text-red-700'
                            : valueSeverity === 'warning'
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-blue-100 text-blue-700'
                        }`}>
                          {valueSeverity}
                        </span>
                        <span>{value}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!code || !text || addMutation.isPending || updateMutation.isPending}
          >
            {(addMutation.isPending || updateMutation.isPending)
              ? 'Saving...'
              : isEditing
              ? 'Save Changes'
              : 'Add Question'}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

function EditorSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div>
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-8 w-64 mt-2" />
        </div>
      </div>

      <Skeleton className="h-16 w-full rounded-lg" />
      <Skeleton className="h-16 w-full rounded-lg" />

      <div className="space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>
    </div>
  );
}
