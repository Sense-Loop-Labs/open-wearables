/**
 * Patient Plan Editor Page
 * Allows customization of an assigned instruction plan for a specific patient
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
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
  Check,
  ChevronDown,
  ChevronRight,
  Edit2,
  GripVertical,
  Loader2,
  Plus,
  RotateCcw,
  Save,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';

// SL-specific components with explicit colors for portal visibility
import { SlBadge } from '@/components/sl/ui/sl-badge';
import { SlInput } from '@/components/sl/ui/sl-input';
import { SlLabel } from '@/components/sl/ui/sl-label';
import { SlTextarea } from '@/components/sl/ui/sl-textarea';
import {
  SlDialog,
  SlDialogContent,
  SlDialogDescription,
  SlDialogFooter,
  SlDialogHeader,
  SlDialogTitle,
} from '@/components/sl/ui/sl-dialog';
import {
  SlSelect,
  SlSelectContent,
  SlSelectItem,
  SlSelectTrigger,
  SlSelectValue,
} from '@/components/sl/ui/sl-select';

import {
  usePatientPlanContent,
  usePatientPlan,
  useUpdatePatientPlan,
} from '@/hooks/api/use-sl-instruction-templates';
import { useSlPatient } from '@/hooks/api/use-sl-patients';
import type {
  TimingConfig,
  PlanCustomizations,
  PlanItemCustomization,
  ResolvedPlanItem,
  ResolvedPlanSection,
} from '@/lib/api/types/sense-loop';

export const Route = createFileRoute(
  '/sl/_sl-authenticated/patients/$patientId/plans/$planId/edit'
)({
  component: PatientPlanEditorPage,
});

// ============================================================================
// Types
// ============================================================================

interface EditorState {
  customizations: PlanCustomizations;
  expandedSections: string[];
  editingItemId: string | null;
}

// ============================================================================
// Main Component
// ============================================================================

function PatientPlanEditorPage() {
  const { patientId, planId } = Route.useParams();
  const navigate = useNavigate();

  const { data: patient, isLoading: patientLoading } = useSlPatient(patientId);
  const { data: plan, isLoading: planLoading } = usePatientPlan(
    patientId,
    planId
  );
  const { data: planContent, isLoading: contentLoading } =
    usePatientPlanContent(patientId, planId);
  const updatePlanMutation = useUpdatePatientPlan();

  const [editorState, setEditorState] = useState<EditorState>({
    customizations: {
      sections: {},
      added_items: [],
      removed_items: [],
      section_order: [],
    },
    expandedSections: [],
    editingItemId: null,
  });
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Initialize editor state from existing customizations
  useEffect(() => {
    if (planContent && !hasInitialized) {
      const existingCustomizations = planContent.customizations || {};
      const sectionIds = planContent.content?.sections?.map((s) => s.id) || [];
      setEditorState({
        customizations: {
          sections: existingCustomizations.sections || {},
          added_items: existingCustomizations.added_items || [],
          removed_items: existingCustomizations.removed_items || [],
          section_order: existingCustomizations.section_order || sectionIds,
        },
        expandedSections: sectionIds,
        editingItemId: null,
      });
      setHasInitialized(true);
    }
  }, [planContent, hasInitialized]);

  // Check if there are unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    if (!planContent) return false;
    const original = planContent.customizations || {};
    const current = editorState.customizations;

    // Compare sections
    const origSections = JSON.stringify(original.sections || {});
    const currSections = JSON.stringify(current.sections || {});
    if (origSections !== currSections) return true;

    // Compare removed items
    const origRemoved = JSON.stringify(original.removed_items || []);
    const currRemoved = JSON.stringify(current.removed_items || []);
    if (origRemoved !== currRemoved) return true;

    // Compare added items
    const origAdded = JSON.stringify(original.added_items || []);
    const currAdded = JSON.stringify(current.added_items || []);
    if (origAdded !== currAdded) return true;

    // Compare section order
    const defaultOrder = planContent.content?.sections?.map((s) => s.id) || [];
    const origOrder = JSON.stringify(original.section_order || defaultOrder);
    const currOrder = JSON.stringify(current.section_order || defaultOrder);
    if (origOrder !== currOrder) return true;

    return false;
  }, [planContent, editorState.customizations]);

  // Handlers
  const toggleSection = useCallback((sectionId: string) => {
    setEditorState((prev) => ({
      ...prev,
      expandedSections: prev.expandedSections.includes(sectionId)
        ? prev.expandedSections.filter((id) => id !== sectionId)
        : [...prev.expandedSections, sectionId],
    }));
  }, []);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setEditorState((prev) => {
        const currentOrder = prev.customizations.section_order || [];
        const oldIndex = currentOrder.indexOf(active.id as string);
        const newIndex = currentOrder.indexOf(over.id as string);

        if (oldIndex === -1 || newIndex === -1) return prev;

        const newOrder = arrayMove(currentOrder, oldIndex, newIndex);

        return {
          ...prev,
          customizations: {
            ...prev.customizations,
            section_order: newOrder,
          },
        };
      });
    }
  }, []);

  const toggleItemEnabled = useCallback((itemId: string) => {
    setEditorState((prev) => {
      const removedItems = prev.customizations.removed_items || [];
      const isCurrentlyDisabled = removedItems.includes(itemId);

      return {
        ...prev,
        customizations: {
          ...prev.customizations,
          removed_items: isCurrentlyDisabled
            ? removedItems.filter((id) => id !== itemId)
            : [...removedItems, itemId],
        },
      };
    });
  }, []);

  const updateItemCustomization = useCallback(
    (
      sectionId: string,
      itemId: string,
      customization: PlanItemCustomization | null
    ) => {
      setEditorState((prev) => {
        const sections = { ...prev.customizations.sections };

        if (customization === null) {
          // Remove customization (reset to default)
          if (sections[sectionId]) {
            const { [itemId]: _, ...remainingItems } =
              sections[sectionId].items || {};
            if (Object.keys(remainingItems).length === 0) {
              // Remove section if no items left
              const { [sectionId]: __, ...remainingSections } = sections;
              return {
                ...prev,
                customizations: {
                  ...prev.customizations,
                  sections: remainingSections,
                },
              };
            }
            sections[sectionId] = {
              ...sections[sectionId],
              items: remainingItems,
            };
          }
        } else {
          // Add or update customization
          if (!sections[sectionId]) {
            sections[sectionId] = { items: {} };
          }
          sections[sectionId] = {
            ...sections[sectionId],
            items: {
              ...sections[sectionId].items,
              [itemId]: customization,
            },
          };
        }

        return {
          ...prev,
          customizations: { ...prev.customizations, sections },
        };
      });
    },
    []
  );

  const handleSave = useCallback(async () => {
    try {
      await updatePlanMutation.mutateAsync({
        patientId,
        planId,
        data: {
          customizations: editorState.customizations,
          regenerate_tasks: true,
        },
      });
      setSaveDialogOpen(false);
      navigate({ to: '/sl/patients/$patientId', params: { patientId } });
    } catch {
      // Error handled by mutation
    }
  }, [
    editorState.customizations,
    patientId,
    planId,
    updatePlanMutation,
    navigate,
  ]);

  const handleCancel = useCallback(() => {
    if (hasUnsavedChanges) {
      if (
        !window.confirm(
          'You have unsaved changes. Are you sure you want to leave?'
        )
      ) {
        return;
      }
    }
    navigate({ to: '/sl/patients/$patientId', params: { patientId } });
  }, [hasUnsavedChanges, navigate, patientId]);

  // Warn on page unload with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Loading state
  const isLoading = patientLoading || planLoading || contentLoading;

  if (isLoading) {
    return <EditorSkeleton />;
  }

  if (!patient || !plan || !planContent) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Plan not found</h2>
        <p className="text-gray-500 mt-2">
          The plan you're looking for doesn't exist or has been deleted.
        </p>
        <Button asChild className="mt-4">
          <Link to="/sl/patients/$patientId" params={{ patientId }}>
            Back to Patient
          </Link>
        </Button>
      </div>
    );
  }

  // Only allow editing active plans
  if (plan.status !== 'active') {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">
          Cannot Edit Plan
        </h2>
        <p className="text-gray-500 mt-2">
          Only active plans can be edited. This plan is {plan.status}.
        </p>
        <Button asChild className="mt-4">
          <Link to="/sl/patients/$patientId" params={{ patientId }}>
            Back to Patient
          </Link>
        </Button>
      </div>
    );
  }

  const sections = planContent.content?.sections || [];

  // Sort sections by custom order
  const sectionOrder =
    editorState.customizations.section_order || sections.map((s) => s.id);
  const orderedSections = [...sections].sort((a, b) => {
    const aIndex = sectionOrder.indexOf(a.id);
    const bIndex = sectionOrder.indexOf(b.id);
    // If not in order array, put at end
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleCancel}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Link to="/sl/patients" className="hover:text-gray-700">
                Patients
              </Link>
              <span>/</span>
              <Link
                to="/sl/patients/$patientId"
                params={{ patientId }}
                className="hover:text-gray-700"
              >
                {patient.full_name}
              </Link>
              <span>/</span>
              <span className="text-gray-900">
                {planContent.template_title}
              </span>
            </div>
            <h1 className="text-2xl font-semibold text-gray-900 mt-1">
              Edit Care Plan
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasUnsavedChanges && (
            <SlBadge
              variant="outline"
              className="text-amber-600 border-amber-300"
            >
              Unsaved changes
            </SlBadge>
          )}
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            onClick={() => setSaveDialogOpen(true)}
            disabled={!hasUnsavedChanges}
          >
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </div>

      {/* Plan Status */}
      <div className="flex items-center gap-3 p-4 bg-white border border-gray-200 rounded-lg">
        <div className="flex-1">
          <p className="font-medium text-gray-900">
            {planContent.template_title}
          </p>
          <p className="text-sm text-gray-500">
            Started{' '}
            {new Date(plan.effective_start).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
            {plan.effective_end && (
              <>
                {' '}
                · Ends{' '}
                {new Date(plan.effective_end).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </>
            )}
          </p>
        </div>
        <PlanStatusBadge status={plan.status} />
      </div>

      {/* Sections */}
      {sections.length === 0 ? (
        <div className="text-center py-12 bg-white border border-gray-200 rounded-lg">
          <p className="text-gray-500">No sections in this plan.</p>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={sectionOrder}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-4">
              {orderedSections.map((section) => (
                <SortableSectionAccordion
                  key={section.id}
                  section={section}
                  isExpanded={editorState.expandedSections.includes(section.id)}
                  onToggle={() => toggleSection(section.id)}
                  customizations={editorState.customizations}
                  removedItems={editorState.customizations.removed_items || []}
                  onToggleItem={toggleItemEnabled}
                  onEditItem={(itemId) =>
                    setEditorState((prev) => ({
                      ...prev,
                      editingItemId: itemId,
                    }))
                  }
                  onResetItem={(itemId) =>
                    updateItemCustomization(section.id, itemId, null)
                  }
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* Edit Item Dialog */}
      <EditItemDialog
        open={!!editorState.editingItemId}
        onOpenChange={(open) => {
          if (!open)
            setEditorState((prev) => ({ ...prev, editingItemId: null }));
        }}
        itemId={editorState.editingItemId}
        sections={sections}
        customizations={editorState.customizations}
        onSave={(sectionId, itemId, customization) => {
          updateItemCustomization(sectionId, itemId, customization);
          setEditorState((prev) => ({ ...prev, editingItemId: null }));
        }}
      />

      {/* Save Confirmation Dialog */}
      <SaveConfirmationDialog
        open={saveDialogOpen}
        onOpenChange={setSaveDialogOpen}
        onConfirm={handleSave}
        isPending={updatePlanMutation.isPending}
      />
    </div>
  );
}

// ============================================================================
// Sortable Section Accordion
// ============================================================================

interface SortableSectionAccordionProps {
  section: ResolvedPlanSection;
  isExpanded: boolean;
  onToggle: () => void;
  customizations: PlanCustomizations;
  removedItems: string[];
  onToggleItem: (itemId: string) => void;
  onEditItem: (itemId: string) => void;
  onResetItem: (itemId: string) => void;
}

function SortableSectionAccordion({
  section,
  isExpanded,
  onToggle,
  customizations,
  removedItems,
  onToggleItem,
  onEditItem,
  onResetItem,
}: SortableSectionAccordionProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: section.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const items = section.items || [];

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-white border border-gray-200 rounded-lg overflow-hidden"
    >
      <div className="flex items-center">
        {/* Drag Handle */}
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing p-4 hover:bg-gray-100 border-r border-gray-200"
          onClick={(e) => e.stopPropagation()}
        >
          <GripVertical className="h-4 w-4 text-gray-400" />
        </div>

        {/* Toggle Button */}
        <button
          type="button"
          onClick={onToggle}
          className="flex-1 flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-3">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400" />
            )}
            <div className="text-left">
              <p className="font-medium text-gray-900">{section.title}</p>
              {section.description && (
                <p className="text-sm text-gray-500">{section.description}</p>
              )}
            </div>
          </div>
          <SlBadge variant="outline" className="text-xs">
            {items.length} {items.length === 1 ? 'item' : 'items'}
          </SlBadge>
        </button>
      </div>

      {isExpanded && (
        <div className="border-t border-gray-200 p-4 space-y-3">
          {items.map((item) => (
            <PlanItemCard
              key={item.id}
              item={item}
              sectionId={section.id}
              isDisabled={removedItems.includes(item.id)}
              customization={
                customizations.sections?.[section.id]?.items?.[item.id]
              }
              onToggle={() => onToggleItem(item.id)}
              onEdit={() => onEditItem(item.id)}
              onReset={() => onResetItem(item.id)}
            />
          ))}
          {items.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">
              No items in this section
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Plan Item Card
// ============================================================================

interface PlanItemCardProps {
  item: ResolvedPlanItem;
  sectionId: string;
  isDisabled: boolean;
  customization?: PlanItemCustomization;
  onToggle: () => void;
  onEdit: () => void;
  onReset: () => void;
}

function PlanItemCard({
  item,
  isDisabled,
  customization,
  onToggle,
  onEdit,
  onReset,
}: PlanItemCardProps) {
  const isCustomized = !!customization && Object.keys(customization).length > 0;

  // Compute displayed values (customized or default)
  const displayTitle = customization?.title || item.title;
  const displayTiming = customization?.timing
    ? { ...item.timing, ...customization.timing }
    : item.timing;

  return (
    <div
      className={`flex items-start gap-4 p-4 rounded-lg border transition-colors ${
        isDisabled
          ? 'bg-gray-50 border-gray-200 opacity-60'
          : 'bg-white border-gray-200 hover:border-gray-300'
      }`}
    >
      {/* Toggle */}
      <div className="pt-0.5">
        <Switch
          checked={!isDisabled}
          onCheckedChange={onToggle}
          aria-label={isDisabled ? 'Enable item' : 'Disable item'}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p
            className={`font-medium ${
              isDisabled ? 'text-gray-400 line-through' : 'text-gray-900'
            }`}
          >
            {displayTitle}
          </p>
          {isCustomized && (
            <SlBadge className="text-xs bg-blue-100 text-blue-700 border-blue-200">
              CUSTOMIZED
            </SlBadge>
          )}
          {isDisabled && (
            <SlBadge className="text-xs bg-gray-100 text-gray-500 border-gray-200">
              DISABLED
            </SlBadge>
          )}
        </div>
        <p
          className={`text-sm mt-1 ${
            isDisabled ? 'text-gray-400 line-through' : 'text-gray-500'
          }`}
        >
          {formatTimingDisplay(displayTiming)}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {isCustomized && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="text-gray-500 hover:text-gray-700"
            title="Reset to default"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={onEdit}
          disabled={isDisabled}
        >
          <Edit2 className="h-4 w-4 mr-1" />
          Edit
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Edit Item Dialog
// ============================================================================

interface EditItemDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  itemId: string | null;
  sections: ResolvedPlanSection[];
  customizations: PlanCustomizations;
  onSave: (
    sectionId: string,
    itemId: string,
    customization: PlanItemCustomization
  ) => void;
}

function EditItemDialog({
  open,
  onOpenChange,
  itemId,
  sections,
  customizations,
  onSave,
}: EditItemDialogProps) {
  // Find item and section
  let foundItem: ResolvedPlanItem | null = null;
  let foundSectionId: string | null = null;

  for (const section of sections) {
    const item = section.items?.find((i) => i.id === itemId);
    if (item) {
      foundItem = item;
      foundSectionId = section.id;
      break;
    }
  }

  const existingCustomization =
    foundSectionId && itemId
      ? customizations.sections?.[foundSectionId]?.items?.[itemId]
      : undefined;

  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [frequency, setFrequency] = useState<number | ''>(1);
  const [periodUnit, setPeriodUnit] = useState<'d' | 'wk' | 'mo'>('d');
  const [timeOfDay, setTimeOfDay] = useState<string[]>([]);
  const [boundsDurationDays, setBoundsDurationDays] = useState<number | ''>('');

  // Reset form when opening
  useEffect(() => {
    if (open && foundItem) {
      const timing = existingCustomization?.timing || foundItem.timing;
      setTitle(existingCustomization?.title || '');
      setDescription(existingCustomization?.description || '');
      setFrequency(timing?.frequency || 1);
      setPeriodUnit(timing?.periodUnit || 'd');
      setTimeOfDay(timing?.timeOfDay || []);
      setBoundsDurationDays(timing?.boundsDurationDays || '');
    }
  }, [open, foundItem, existingCustomization]);

  const handleSubmit = () => {
    if (!itemId || !foundSectionId) return;

    const customization: PlanItemCustomization = {};

    // Only include changed values
    if (title) customization.title = title;
    if (description) customization.description = description;

    // Build timing customization
    const timingCustomization: Partial<TimingConfig> = {};
    if (frequency !== '' && frequency !== foundItem?.timing?.frequency) {
      timingCustomization.frequency = frequency;
    }
    if (periodUnit !== foundItem?.timing?.periodUnit) {
      timingCustomization.periodUnit = periodUnit;
    }
    if (
      JSON.stringify(timeOfDay) !==
      JSON.stringify(foundItem?.timing?.timeOfDay || [])
    ) {
      timingCustomization.timeOfDay = timeOfDay;
    }
    if (
      boundsDurationDays !== '' &&
      boundsDurationDays !== foundItem?.timing?.boundsDurationDays
    ) {
      timingCustomization.boundsDurationDays = boundsDurationDays;
    }

    if (Object.keys(timingCustomization).length > 0) {
      customization.timing = timingCustomization;
    }

    onSave(foundSectionId, itemId, customization);
  };

  const handleAddTime = () => {
    const newTime = '09:00';
    if (!timeOfDay.includes(newTime)) {
      setTimeOfDay([...timeOfDay, newTime]);
    }
  };

  const handleRemoveTime = (index: number) => {
    setTimeOfDay(timeOfDay.filter((_, i) => i !== index));
  };

  const handleUpdateTime = (index: number, value: string) => {
    const newTimes = [...timeOfDay];
    newTimes[index] = value;
    setTimeOfDay(newTimes);
  };

  if (!foundItem) return null;

  return (
    <SlDialog open={open} onOpenChange={onOpenChange}>
      <SlDialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <SlDialogHeader>
          <SlDialogTitle>Edit Activity</SlDialogTitle>
          <SlDialogDescription>
            Customize timing and content for this activity
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-6 py-4">
          {/* Default info */}
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Template default:</p>
            <p className="font-medium text-gray-900">{foundItem.title}</p>
            <p className="text-sm text-gray-500">
              {formatTimingDisplay(foundItem.timing)}
            </p>
          </div>

          {/* Title override */}
          <div className="space-y-2">
            <SlLabel htmlFor="edit-title">
              Custom Title{' '}
              <span className="text-gray-400 font-normal">(optional)</span>
            </SlLabel>
            <SlInput
              id="edit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={foundItem.title}
            />
          </div>

          {/* Timing: Frequency */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <SlLabel htmlFor="edit-frequency">Frequency</SlLabel>
              <SlInput
                id="edit-frequency"
                type="number"
                min={1}
                value={frequency}
                onChange={(e) =>
                  setFrequency(
                    e.target.value ? parseInt(e.target.value, 10) : ''
                  )
                }
              />
            </div>
            <div className="space-y-2">
              <SlLabel htmlFor="edit-period">Period</SlLabel>
              <SlSelect
                value={periodUnit}
                onValueChange={(v) => setPeriodUnit(v as 'd' | 'wk' | 'mo')}
              >
                <SlSelectTrigger id="edit-period">
                  <SlSelectValue />
                </SlSelectTrigger>
                <SlSelectContent>
                  <SlSelectItem value="d">Daily</SlSelectItem>
                  <SlSelectItem value="wk">Weekly</SlSelectItem>
                  <SlSelectItem value="mo">Monthly</SlSelectItem>
                </SlSelectContent>
              </SlSelect>
            </div>
          </div>

          {/* Timing: Time of Day */}
          <div className="space-y-2">
            <SlLabel>Time of Day</SlLabel>
            <div className="space-y-2">
              {timeOfDay.map((time, index) => (
                <div key={index} className="flex items-center gap-2">
                  <SlInput
                    type="time"
                    value={time}
                    onChange={(e) => handleUpdateTime(index, e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveTime(index)}
                  >
                    <X className="h-4 w-4 text-gray-500" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={handleAddTime}
                className="w-full"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Time
              </Button>
            </div>
          </div>

          {/* Timing: Duration */}
          <div className="space-y-2">
            <SlLabel htmlFor="edit-duration">
              Duration (days){' '}
              <span className="text-gray-400 font-normal">(optional)</span>
            </SlLabel>
            <SlInput
              id="edit-duration"
              type="number"
              min={1}
              value={boundsDurationDays}
              onChange={(e) =>
                setBoundsDurationDays(
                  e.target.value ? parseInt(e.target.value, 10) : ''
                )
              }
              placeholder="Ongoing"
            />
          </div>

          {/* Description override */}
          <div className="space-y-2">
            <SlLabel htmlFor="edit-description">
              Custom Description{' '}
              <span className="text-gray-400 font-normal">(optional)</span>
            </SlLabel>
            <SlTextarea
              id="edit-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={foundItem.description || 'No description'}
              rows={2}
            />
          </div>
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit}>
            <Check className="h-4 w-4 mr-2" />
            Apply Changes
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

// ============================================================================
// Save Confirmation Dialog
// ============================================================================

interface SaveConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending: boolean;
}

function SaveConfirmationDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
}: SaveConfirmationDialogProps) {
  return (
    <SlDialog open={open} onOpenChange={onOpenChange}>
      <SlDialogContent>
        <SlDialogHeader>
          <SlDialogTitle>Save Changes</SlDialogTitle>
          <SlDialogDescription>
            Are you sure you want to save these customizations?
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="py-4">
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-sm text-amber-800">
              <strong>Note:</strong> Saving these changes will regenerate all
              pending tasks for this patient based on the new schedule.
              Completed tasks will not be affected.
            </p>
          </div>
        </div>

        <SlDialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={isPending}>
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save & Regenerate Tasks
              </>
            )}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

// ============================================================================
// Helper Components
// ============================================================================

function PlanStatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    active: {
      label: 'Active',
      className: 'bg-green-100 text-green-800',
    },
    completed: {
      label: 'Completed',
      className: 'bg-gray-100 text-gray-800',
    },
    cancelled: {
      label: 'Cancelled',
      className: 'bg-red-100 text-red-800',
    },
  };

  const { label, className } = config[status] || {
    label: status,
    className: 'bg-gray-100 text-gray-800',
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function EditorSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded" />
        <div>
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-8 w-64 mt-2" />
        </div>
      </div>
      <Skeleton className="h-20 rounded-lg" />
      <Skeleton className="h-64 rounded-lg" />
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatTimingDisplay(timing?: TimingConfig): string {
  if (!timing) return 'As needed';

  const parts: string[] = [];

  // Frequency
  if (timing.frequency && timing.frequency > 1) {
    parts.push(`${timing.frequency}x`);
  }

  // Period
  if (timing.periodUnit) {
    const unitMap: Record<string, string> = {
      d: 'daily',
      wk: 'weekly',
      mo: 'monthly',
    };
    parts.push(unitMap[timing.periodUnit] || timing.periodUnit);
  }

  // Time of day
  if (timing.timeOfDay?.length) {
    const formattedTimes = timing.timeOfDay.map((t) => {
      const [hours, minutes] = t.split(':');
      const h = parseInt(hours, 10);
      const ampm = h >= 12 ? 'PM' : 'AM';
      const h12 = h % 12 || 12;
      return `${h12}:${minutes} ${ampm}`;
    });
    parts.push(`at ${formattedTimes.join(', ')}`);
  }

  // Duration
  if (timing.boundsDurationDays) {
    parts.push(`· ${timing.boundsDurationDays} days`);
  } else if (timing.boundsType === 'ongoing') {
    parts.push('· Ongoing');
  }

  return parts.length > 0 ? parts.join(' ') : 'As needed';
}
