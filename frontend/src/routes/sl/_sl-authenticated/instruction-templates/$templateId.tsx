import { useState } from 'react';
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
  Edit2,
  CheckCircle,
  Archive,
  Copy,
  Plus,
  GripVertical,
  Trash2,
  Settings,
  Clock,
  Activity,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

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
  useInstructionTemplate,
  useInstructionTemplatePreview,
  useUpdateInstructionTemplate,
  useActivateInstructionTemplate,
  useRetireInstructionTemplate,
  useDuplicateInstructionTemplate,
  useActivityTemplates,
} from '@/hooks/api/use-sl-instruction-templates';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import type { InstructionTemplate, ActivityTemplate } from '@/lib/api/types/sense-loop';

export const Route = createFileRoute(
  '/sl/_sl-authenticated/instruction-templates/$templateId'
)({
  component: InstructionTemplateDetailPage,
});

function InstructionTemplateDetailPage() {
  const { templateId } = Route.useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('content');
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const { data: template, isLoading } = useInstructionTemplate(templateId);
  const { data: preview } = useInstructionTemplatePreview(templateId);

  const activateMutation = useActivateInstructionTemplate();
  const retireMutation = useRetireInstructionTemplate();
  const duplicateMutation = useDuplicateInstructionTemplate();

  if (isLoading) {
    return <TemplateDetailSkeleton />;
  }

  if (!template) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">
          Template not found
        </h2>
        <p className="text-gray-500 mt-2">
          The template you're looking for doesn't exist or has been deleted.
        </p>
        <Button asChild className="mt-4">
          <Link to="/sl/instruction-templates">Back to Templates</Link>
        </Button>
      </div>
    );
  }

  const handleDuplicate = () => {
    duplicateMutation.mutate(
      { id: templateId },
      {
        onSuccess: (newTemplate) => {
          navigate({
            to: '/sl/instruction-templates/$templateId',
            params: { templateId: newTemplate.id },
          });
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/sl/instruction-templates">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-gray-900">
                {template.title}
              </h1>
              <StatusBadge status={template.status} />
              {!template.organization_id && (
                <SlBadge variant="outline">Shared</SlBadge>
              )}
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {template.description}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setIsEditDialogOpen(true)}
          >
            <Edit2 className="h-4 w-4 mr-2" />
            Edit
          </Button>
          <Button variant="outline" onClick={handleDuplicate}>
            <Copy className="h-4 w-4 mr-2" />
            Duplicate
          </Button>
          {template.status === 'draft' && (
            <Button onClick={() => activateMutation.mutate(templateId)}>
              <CheckCircle className="h-4 w-4 mr-2" />
              Activate
            </Button>
          )}
          {template.status === 'active' && (
            <Button
              variant="destructive"
              onClick={() => retireMutation.mutate(templateId)}
            >
              <Archive className="h-4 w-4 mr-2" />
              Retire
            </Button>
          )}
        </div>
      </div>

      {/* Metadata Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetadataCard
          title="Version"
          value={template.version}
          icon={<Settings className="h-4 w-4" />}
        />
        <MetadataCard
          title="Sections"
          value={template.content?.sections?.length || 0}
          icon={<GripVertical className="h-4 w-4" />}
        />
        <MetadataCard
          title="Health Focus Areas"
          value={template.health_focus_codes?.length || 0}
          icon={<Activity className="h-4 w-4" />}
        />
        <MetadataCard
          title="Created"
          value={new Date(template.created_at).toLocaleDateString()}
          icon={<Clock className="h-4 w-4" />}
        />
      </div>

      {/* Health Focus Tags */}
      {template.health_focus_codes && template.health_focus_codes.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-500">
            Health Focus:
          </span>
          {template.health_focus_codes.map((code) => (
            <SlBadge key={code} variant="secondary">
              {code.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </SlBadge>
          ))}
        </div>
      )}

      {/* Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="content" className="mt-4">
          <ContentEditor template={template} />
        </TabsContent>

        <TabsContent value="preview" className="mt-4">
          <ContentPreview preview={preview} />
        </TabsContent>

        <TabsContent value="settings" className="mt-4">
          <TemplateSettings template={template} />
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <EditTemplateDialog
        template={template}
        open={isEditDialogOpen}
        onOpenChange={setIsEditDialogOpen}
      />
    </div>
  );
}

function MetadataCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center gap-2 text-gray-400">
        {icon}
        <span className="text-sm">{title}</span>
      </div>
      <p className="text-lg font-semibold text-gray-900 mt-1">
        {value}
      </p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, { className: string; label: string }> = {
    active: { className: 'bg-green-500/10 text-green-500', label: 'Active' },
    draft: { className: 'bg-yellow-500/10 text-yellow-500', label: 'Draft' },
    retired: { className: 'bg-gray-500/10 text-gray-500', label: 'Retired' },
  };

  const variant = variants[status] || variants.draft;

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${variant.className}`}>
      {variant.label}
    </span>
  );
}

function ContentEditor({ template }: { template: InstructionTemplate }) {
  const organizationId = getSlCurrentOrgId();
  const updateMutation = useUpdateInstructionTemplate();
  const { data: activitiesData } = useActivityTemplates({
    organization_id: organizationId || undefined,
    include_shared: true,
    status: 'active',
  });

  const [isAddSectionOpen, setIsAddSectionOpen] = useState(false);
  const [isAddItemOpen, setIsAddItemOpen] = useState(false);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);

  const sections = template.content?.sections || [];
  const availableActivities = activitiesData?.items || [];

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

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = sections.findIndex((s: any) => s.id === active.id);
      const newIndex = sections.findIndex((s: any) => s.id === over.id);

      const reorderedSections = arrayMove(sections, oldIndex, newIndex);

      const updatedContent = {
        ...template.content,
        sections: reorderedSections,
      };

      updateMutation.mutate({ id: template.id, data: { content: updatedContent } });
    }
  };

  const handleAddSection = (title: string, description: string, activityIds: string[]) => {
    const newSection = {
      id: crypto.randomUUID(),
      title,
      description: description || undefined,
      items: activityIds.map((activityId) => ({
        id: crypto.randomUUID(),
        type: 'activity_ref',
        activity_template_id: activityId,
      })),
    };

    const updatedContent = {
      ...template.content,
      sections: [...sections, newSection],
    };

    updateMutation.mutate(
      { id: template.id, data: { content: updatedContent } },
      { onSuccess: () => setIsAddSectionOpen(false) }
    );
  };

  const handleAddItem = (activityId: string) => {
    if (!selectedSectionId) return;

    const newItem = {
      id: crypto.randomUUID(),
      type: 'activity_ref',
      activity_template_id: activityId,
    };

    const updatedSections = sections.map((section: any) => {
      if (section.id === selectedSectionId) {
        return {
          ...section,
          items: [...(section.items || []), newItem],
        };
      }
      return section;
    });

    const updatedContent = {
      ...template.content,
      sections: updatedSections,
    };

    updateMutation.mutate(
      { id: template.id, data: { content: updatedContent } },
      {
        onSuccess: () => {
          setIsAddItemOpen(false);
          setSelectedSectionId(null);
        },
      }
    );
  };

  const handleRemoveItem = (sectionId: string, itemId: string) => {
    const updatedSections = sections.map((section: any) => {
      if (section.id === sectionId) {
        return {
          ...section,
          items: (section.items || []).filter((item: any) => item.id !== itemId),
        };
      }
      return section;
    });

    const updatedContent = {
      ...template.content,
      sections: updatedSections,
    };

    updateMutation.mutate({ id: template.id, data: { content: updatedContent } });
  };

  const handleRemoveSection = (sectionId: string) => {
    const updatedSections = sections.filter((section: any) => section.id !== sectionId);

    const updatedContent = {
      ...template.content,
      sections: updatedSections,
    };

    updateMutation.mutate({ id: template.id, data: { content: updatedContent } });
  };

  const openAddItem = (sectionId: string) => {
    setSelectedSectionId(sectionId);
    setIsAddItemOpen(true);
  };

  if (sections.length === 0) {
    return (
      <>
        <Card className="bg-white">
          <CardContent className="py-12 text-center">
            <Plus className="h-12 w-12 mx-auto text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No sections yet
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              Add sections to organize your instruction template
            </p>
            <Button className="mt-4" onClick={() => setIsAddSectionOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Section
            </Button>
          </CardContent>
        </Card>

        <AddSectionDialog
          open={isAddSectionOpen}
          onOpenChange={setIsAddSectionOpen}
          onAdd={handleAddSection}
          activities={availableActivities}
          isPending={updateMutation.isPending}
        />
      </>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">
            Sections
          </h3>
          <Button size="sm" onClick={() => setIsAddSectionOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Section
          </Button>
        </div>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={sections.map((s: any) => s.id)}
            strategy={verticalListSortingStrategy}
          >
            <Accordion type="multiple" className="space-y-2">
              {sections.map((section: any, index: number) => (
                <SortableSectionItem
                  key={section.id}
                  section={section}
                  index={index}
                  availableActivities={availableActivities}
                  onRemoveItem={handleRemoveItem}
                  onRemoveSection={handleRemoveSection}
                  onAddItem={openAddItem}
                  isPending={updateMutation.isPending}
                />
              ))}
            </Accordion>
          </SortableContext>
        </DndContext>
      </div>

      <AddSectionDialog
        open={isAddSectionOpen}
        onOpenChange={setIsAddSectionOpen}
        onAdd={handleAddSection}
        activities={availableActivities}
        isPending={updateMutation.isPending}
      />

      <AddItemDialog
        open={isAddItemOpen}
        onOpenChange={(open) => {
          setIsAddItemOpen(open);
          if (!open) setSelectedSectionId(null);
        }}
        onAdd={handleAddItem}
        activities={availableActivities}
        isPending={updateMutation.isPending}
      />
    </>
  );
}

function SortableSectionItem({
  section,
  index,
  availableActivities,
  onRemoveItem,
  onRemoveSection,
  onAddItem,
  isPending,
}: {
  section: any;
  index: number;
  availableActivities: ActivityTemplate[];
  onRemoveItem: (sectionId: string, itemId: string) => void;
  onRemoveSection: (sectionId: string) => void;
  onAddItem: (sectionId: string) => void;
  isPending: boolean;
}) {
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

  return (
    <div ref={setNodeRef} style={style}>
      <AccordionItem
        value={section.id || `section-${index}`}
        className="bg-white border border-gray-200 rounded-lg"
      >
        <AccordionTrigger className="px-4 hover:no-underline">
          <div className="flex items-center gap-3">
            <div
              {...attributes}
              {...listeners}
              className="cursor-grab active:cursor-grabbing p-1 -m-1 rounded hover:bg-gray-100"
              onClick={(e) => e.stopPropagation()}
            >
              <GripVertical className="h-4 w-4 text-gray-400" />
            </div>
            <span className="font-medium text-gray-900">{section.title || `Section ${index + 1}`}</span>
            <SlBadge variant="outline" className="text-xs">
              {section.items?.length || 0} items
            </SlBadge>
          </div>
        </AccordionTrigger>
        <AccordionContent className="px-4 pb-4">
          <div className="space-y-2 mt-2">
            {section.description && (
              <p className="text-sm text-gray-500 mb-3">{section.description}</p>
            )}
            {section.items?.map((item: any, itemIndex: number) => {
              const activity = availableActivities.find(
                (a) => a.id === item.activity_template_id
              );
              return (
                <div
                  key={item.id || itemIndex}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-md"
                >
                  <div className="flex items-center gap-3">
                    <Activity className="h-4 w-4 text-gray-400" />
                    <div>
                      <p className="font-medium text-sm text-gray-900">
                        {activity?.title || item.title || 'Unknown Activity'}
                      </p>
                      {activity && (
                        <p className="text-xs text-gray-500">
                          {activity.category_code} • {activity.completion_method}
                        </p>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onRemoveItem(section.id, item.id)}
                    disabled={isPending}
                  >
                    <Trash2 className="h-4 w-4 text-gray-500 hover:text-red-500" />
                  </Button>
                </div>
              );
            })}
            {(!section.items || section.items.length === 0) && (
              <p className="text-sm text-gray-400 text-center py-4">
                No activities in this section
              </p>
            )}
            <div className="flex gap-2 mt-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onAddItem(section.id)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Activity
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRemoveSection(section.id)}
                disabled={isPending}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </div>
  );
}

function AddSectionDialog({
  open,
  onOpenChange,
  onAdd,
  activities,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (title: string, description: string, activityIds: string[]) => void;
  activities: ActivityTemplate[];
  isPending: boolean;
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [selectedActivityIds, setSelectedActivityIds] = useState<string[]>([]);

  const toggleActivity = (activityId: string) => {
    setSelectedActivityIds((prev) =>
      prev.includes(activityId)
        ? prev.filter((id) => id !== activityId)
        : [...prev, activityId]
    );
  };

  const handleSubmit = () => {
    onAdd(title, description, selectedActivityIds);
    setTitle('');
    setDescription('');
    setSelectedActivityIds([]);
  };

  const handleClose = () => {
    onOpenChange(false);
    setTitle('');
    setDescription('');
    setSelectedActivityIds([]);
  };

  return (
    <SlDialog open={open} onOpenChange={handleClose}>
      <SlDialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <SlDialogHeader>
          <SlDialogTitle>Add Section</SlDialogTitle>
          <SlDialogDescription>
            Create a new section and select activities to include
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <SlLabel htmlFor="section-title">Section Title</SlLabel>
            <SlInput
              id="section-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Daily Monitoring, Exercise Routine"
            />
          </div>
          <div className="space-y-2">
            <SlLabel htmlFor="section-description">Description (optional)</SlLabel>
            <SlTextarea
              id="section-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this section..."
              rows={2}
            />
          </div>

          {/* Activity Selection */}
          <div className="space-y-2">
            <SlLabel>
              Select Activities
              {selectedActivityIds.length > 0 && (
                <span className="ml-2 text-blue-600 font-normal">
                  ({selectedActivityIds.length} selected)
                </span>
              )}
            </SlLabel>
            {activities.length === 0 ? (
              <p className="text-sm text-gray-500 py-3 text-center border border-dashed border-gray-300 rounded-lg">
                No active activities available. Create activities first.
              </p>
            ) : (
              <div className="border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
                {activities.map((activity) => {
                  const isSelected = selectedActivityIds.includes(activity.id);
                  return (
                    <button
                      key={activity.id}
                      type="button"
                      onClick={() => toggleActivity(activity.id)}
                      className={`w-full text-left p-3 border-b border-gray-100 last:border-b-0 transition-colors ${
                        isSelected
                          ? 'bg-blue-50 border-l-2 border-l-blue-500'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                          isSelected
                            ? 'bg-blue-600 border-blue-600'
                            : 'border-gray-300'
                        }`}>
                          {isSelected && (
                            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm text-gray-900">{activity.title}</p>
                          <p className="text-xs text-gray-500 truncate">{activity.description}</p>
                        </div>
                        <SlBadge variant="outline" className="text-xs shrink-0">
                          {activity.category_code}
                        </SlBadge>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!title || isPending}>
            {isPending ? 'Adding...' : `Add Section${selectedActivityIds.length > 0 ? ` with ${selectedActivityIds.length} ${selectedActivityIds.length === 1 ? 'Activity' : 'Activities'}` : ''}`}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

function AddItemDialog({
  open,
  onOpenChange,
  onAdd,
  activities,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (activityId: string) => void;
  activities: ActivityTemplate[];
  isPending: boolean;
}) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredActivities = activities.filter(
    (a) =>
      a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.category_code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleClose = () => {
    onOpenChange(false);
    setSearchQuery('');
  };

  return (
    <SlDialog open={open} onOpenChange={handleClose}>
      <SlDialogContent className="max-w-lg">
        <SlDialogHeader>
          <SlDialogTitle>Add Activity</SlDialogTitle>
          <SlDialogDescription>
            Select an activity to add to this section
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="py-4">
          <SlInput
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search activities..."
            className="mb-4"
          />

          <div className="max-h-64 overflow-y-auto space-y-2">
            {filteredActivities.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">
                {activities.length === 0
                  ? 'No active activities available. Create activities first.'
                  : 'No activities match your search.'}
              </p>
            ) : (
              filteredActivities.map((activity) => (
                <button
                  key={activity.id}
                  onClick={() => onAdd(activity.id)}
                  disabled={isPending}
                  className="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-colors disabled:opacity-50"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{activity.title}</p>
                      <p className="text-sm text-gray-500 line-clamp-1">
                        {activity.description}
                      </p>
                    </div>
                    <SlBadge variant="outline" className="text-xs ml-2 shrink-0">
                      {activity.category_code}
                    </SlBadge>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

function ContentPreview({ preview }: { preview: any }) {
  if (!preview) {
    return (
      <Card className="bg-white">
        <CardContent className="py-8 text-center">
          <p className="text-gray-400">Loading preview...</p>
        </CardContent>
      </Card>
    );
  }

  const sections = preview.content?.sections || [];

  return (
    <Card className="bg-white">
      <CardHeader>
        <CardTitle className="text-gray-900">{preview.title}</CardTitle>
        <CardDescription className="text-gray-500">{preview.description}</CardDescription>
      </CardHeader>
      <CardContent>
        {sections.length === 0 ? (
          <p className="text-gray-400">No content to preview</p>
        ) : (
          <div className="space-y-6">
            {sections.map((section: any, index: number) => (
              <div key={section.id || index}>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">{section.title}</h3>
                {section.description && (
                  <p className="text-sm text-gray-500 mb-3">
                    {section.description}
                  </p>
                )}
                <div className="space-y-3">
                  {section.items?.map((item: any, itemIndex: number) => (
                    <div
                      key={item.id || itemIndex}
                      className="p-4 border border-gray-200 rounded-lg"
                    >
                      <h4 className="font-medium text-gray-900">
                        {item.title || item.activity?.title}
                      </h4>
                      <p className="text-sm text-gray-500 mt-1">
                        {item.description || item.activity?.description}
                      </p>
                      {item.timing && (
                        <p className="text-xs text-gray-400 mt-2">
                          Schedule: {formatTiming(item.timing)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TemplateSettings({ template }: { template: InstructionTemplate }) {
  return (
    <div className="space-y-6">
      <Card className="bg-white">
        <CardHeader>
          <CardTitle className="text-gray-900">Notification Settings</CardTitle>
          <CardDescription className="text-gray-500">
            Configure how patients receive notifications for tasks
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">
            {template.notification_config
              ? JSON.stringify(template.notification_config, null, 2)
              : 'Using default notification settings'}
          </p>
        </CardContent>
      </Card>

      <Card className="bg-white">
        <CardHeader>
          <CardTitle className="text-gray-900">Template Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <SlLabel className="text-gray-500">Internal Name</SlLabel>
            <p className="font-mono text-sm text-gray-900">{template.name}</p>
          </div>
          <div>
            <SlLabel className="text-gray-500">Created</SlLabel>
            <p className="text-gray-900">{new Date(template.created_at).toLocaleString()}</p>
          </div>
          <div>
            <SlLabel className="text-gray-500">Last Updated</SlLabel>
            <p className="text-gray-900">{new Date(template.updated_at).toLocaleString()}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function EditTemplateDialog({
  template,
  open,
  onOpenChange,
}: {
  template: InstructionTemplate;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const updateMutation = useUpdateInstructionTemplate();
  const [title, setTitle] = useState(template.title);
  const [description, setDescription] = useState(template.description);

  const handleSubmit = () => {
    updateMutation.mutate(
      { id: template.id, data: { title, description } },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      }
    );
  };

  return (
    <SlDialog open={open} onOpenChange={onOpenChange}>
      <SlDialogContent>
        <SlDialogHeader>
          <SlDialogTitle>Edit Template</SlDialogTitle>
          <SlDialogDescription>
            Update the template title and description
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <SlLabel htmlFor="edit-title">Title</SlLabel>
            <SlInput
              id="edit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <SlLabel htmlFor="edit-description">Description</SlLabel>
            <SlTextarea
              id="edit-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!title || updateMutation.isPending}
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

function formatTiming(timing: any): string {
  if (!timing) return 'As needed';

  const parts: string[] = [];

  if (timing.frequency && timing.frequency > 1) {
    parts.push(`${timing.frequency}x`);
  }

  if (timing.period && timing.periodUnit) {
    const unitMap: Record<string, string> = {
      d: 'daily',
      wk: 'weekly',
      mo: 'monthly',
    };
    parts.push(unitMap[timing.periodUnit] || timing.periodUnit);
  }

  if (timing.timeOfDay?.length) {
    parts.push(`at ${timing.timeOfDay.join(', ')}`);
  }

  return parts.length > 0 ? parts.join(' ') : 'As needed';
}

function TemplateDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded" />
        <div>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96 mt-2" />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-lg" />
    </div>
  );
}
