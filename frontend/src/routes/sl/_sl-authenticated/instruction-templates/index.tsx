import { useState, useEffect } from 'react';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import {
  Plus,
  Search,
  FileText,
  MoreHorizontal,
  Copy,
  Archive,
  CheckCircle,
  Clock,
  Activity,
  Pencil,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

// SL-specific components with explicit colors for portal visibility
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
  SlDropdownMenu,
  SlDropdownMenuContent,
  SlDropdownMenuItem,
  SlDropdownMenuSeparator,
  SlDropdownMenuTrigger,
} from '@/components/sl/ui/sl-dropdown-menu';
import {
  SlDialog,
  SlDialogContent,
  SlDialogDescription,
  SlDialogFooter,
  SlDialogHeader,
  SlDialogTitle,
} from '@/components/sl/ui/sl-dialog';

import {
  useInstructionTemplates,
  useCreateInstructionTemplate,
  useActivateInstructionTemplate,
  useRetireInstructionTemplate,
  useDuplicateInstructionTemplate,
  useActivityTemplates,
  useCreateActivityTemplate,
  useUpdateActivityTemplate,
  useActivateActivityTemplate,
  useRetireActivityTemplate,
} from '@/hooks/api/use-sl-instruction-templates';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import type { InstructionTemplate, ActivityTemplate } from '@/lib/api/types/sense-loop';

export const Route = createFileRoute(
  '/sl/_sl-authenticated/instruction-templates/'
)({
  component: InstructionTemplatesPage,
});

function InstructionTemplatesPage() {
  const organizationId = getSlCurrentOrgId();
  const [activeTab, setActiveTab] = useState<'templates' | 'activities'>('templates');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isCreateActivityDialogOpen, setIsCreateActivityDialogOpen] = useState(false);

  // Queries
  const { data: templatesData, isLoading: isLoadingTemplates } = useInstructionTemplates({
    organization_id: organizationId || undefined,
    include_shared: true,
    status: statusFilter !== 'all' ? (statusFilter as 'draft' | 'active' | 'retired') : undefined,
  });

  const { data: activitiesData, isLoading: isLoadingActivities } = useActivityTemplates({
    organization_id: organizationId || undefined,
    include_shared: true,
    status: statusFilter !== 'all' ? (statusFilter as 'draft' | 'active' | 'retired') : undefined,
  });

  // Filter by search
  const filteredTemplates = templatesData?.items.filter(
    (t) =>
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredActivities = activitiesData?.items.filter(
    (a) =>
      a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats
  const templateStats = {
    total: templatesData?.total || 0,
    active: templatesData?.items.filter((t) => t.status === 'active').length || 0,
    draft: templatesData?.items.filter((t) => t.status === 'draft').length || 0,
  };

  const activityStats = {
    total: activitiesData?.total || 0,
    active: activitiesData?.items.filter((a) => a.status === 'active').length || 0,
    draft: activitiesData?.items.filter((a) => a.status === 'draft').length || 0,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--sl-text-primary)]">
            Instruction Templates
          </h1>
          <p className="text-sm text-[var(--sl-text-secondary)] mt-1">
            Create and manage discharge instructions and care plan templates
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setIsCreateActivityDialogOpen(true)}
            className="border-[var(--sl-border)]"
          >
            <Activity className="h-4 w-4 mr-2" />
            New Activity
          </Button>
          <Button onClick={() => setIsCreateDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Template
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Total Templates"
          value={templateStats.total}
          icon={<FileText className="h-5 w-5" />}
        />
        <StatCard
          title="Active Templates"
          value={templateStats.active}
          icon={<CheckCircle className="h-5 w-5 text-green-500" />}
        />
        <StatCard
          title="Total Activities"
          value={activityStats.total}
          icon={<Activity className="h-5 w-5" />}
        />
        <StatCard
          title="Draft Items"
          value={templateStats.draft + activityStats.draft}
          icon={<Clock className="h-5 w-5 text-yellow-500" />}
        />
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'templates' | 'activities')}>
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="templates">
              Templates ({templateStats.total})
            </TabsTrigger>
            <TabsTrigger value="activities">
              Activities ({activityStats.total})
            </TabsTrigger>
          </TabsList>

          {/* Filters */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--sl-text-muted)]" />
              <SlInput
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-64"
              />
            </div>
            <SlSelect value={statusFilter} onValueChange={setStatusFilter}>
              <SlSelectTrigger className="w-32">
                <SlSelectValue placeholder="Status" />
              </SlSelectTrigger>
              <SlSelectContent>
                <SlSelectItem value="all">All Status</SlSelectItem>
                <SlSelectItem value="active">Active</SlSelectItem>
                <SlSelectItem value="draft">Draft</SlSelectItem>
                <SlSelectItem value="retired">Retired</SlSelectItem>
              </SlSelectContent>
            </SlSelect>
          </div>
        </div>

        <TabsContent value="templates" className="mt-4">
          {isLoadingTemplates ? (
            <TemplateListSkeleton />
          ) : (
            <TemplateList templates={filteredTemplates || []} />
          )}
        </TabsContent>

        <TabsContent value="activities" className="mt-4">
          {isLoadingActivities ? (
            <TemplateListSkeleton />
          ) : (
            <ActivityList activities={filteredActivities || []} />
          )}
        </TabsContent>
      </Tabs>

      {/* Create Template Dialog */}
      <CreateTemplateDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
      />

      {/* Create Activity Dialog */}
      <CreateActivityDialog
        open={isCreateActivityDialogOpen}
        onOpenChange={setIsCreateActivityDialogOpen}
      />
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-[var(--sl-text-secondary)]">{title}</p>
          <p className="text-2xl font-semibold text-[var(--sl-text-primary)] mt-1">
            {value}
          </p>
        </div>
        <div className="text-[var(--sl-text-muted)]">{icon}</div>
      </div>
    </div>
  );
}

function TemplateList({ templates }: { templates: InstructionTemplate[] }) {
  const activateMutation = useActivateInstructionTemplate();
  const retireMutation = useRetireInstructionTemplate();
  const duplicateMutation = useDuplicateInstructionTemplate();

  if (templates.length === 0) {
    return (
      <div className="text-center py-12 bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg">
        <FileText className="h-12 w-12 mx-auto text-[var(--sl-text-muted)]" />
        <h3 className="mt-4 text-lg font-medium text-[var(--sl-text-primary)]">
          No templates found
        </h3>
        <p className="mt-2 text-sm text-[var(--sl-text-secondary)]">
          Create your first instruction template to get started
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {templates.map((template) => (
        <div
          key={template.id}
          className="bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg p-4 hover:border-[var(--sl-border-hover)] transition-colors"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Link
                  to="/sl/instruction-templates/$templateId"
                  params={{ templateId: template.id }}
                  className="text-lg font-medium text-[var(--sl-text-primary)] hover:text-[var(--sl-primary)] transition-colors"
                >
                  {template.title}
                </Link>
                <StatusBadge status={template.status} />
                {!template.organization_id && (
                  <SlBadge variant="outline" className="text-xs">
                    Shared
                  </SlBadge>
                )}
              </div>
              <p className="text-sm text-[var(--sl-text-secondary)] mt-1 line-clamp-2">
                {template.description}
              </p>
              <div className="flex items-center gap-4 mt-3 text-xs text-[var(--sl-text-muted)]">
                <span>Version {template.version}</span>
                <span>
                  {template.health_focus_codes?.length || 0} health focus areas
                </span>
                <span>
                  {template.content?.sections?.length || 0} sections
                </span>
              </div>
            </div>

            <SlDropdownMenu>
              <SlDropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </SlDropdownMenuTrigger>
              <SlDropdownMenuContent align="end">
                <SlDropdownMenuItem asChild>
                  <Link
                    to="/sl/instruction-templates/$templateId"
                    params={{ templateId: template.id }}
                  >
                    View Details
                  </Link>
                </SlDropdownMenuItem>
                <SlDropdownMenuItem
                  onClick={() => duplicateMutation.mutate({ id: template.id })}
                >
                  <Copy className="h-4 w-4 mr-2" />
                  Duplicate
                </SlDropdownMenuItem>
                <SlDropdownMenuSeparator />
                {template.status === 'draft' && (
                  <SlDropdownMenuItem
                    onClick={() => activateMutation.mutate(template.id)}
                  >
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Activate
                  </SlDropdownMenuItem>
                )}
                {template.status === 'active' && (
                  <SlDropdownMenuItem
                    onClick={() => retireMutation.mutate(template.id)}
                    className="text-red-600"
                  >
                    <Archive className="h-4 w-4 mr-2" />
                    Retire
                  </SlDropdownMenuItem>
                )}
              </SlDropdownMenuContent>
            </SlDropdownMenu>
          </div>
        </div>
      ))}
    </div>
  );
}

function ActivityList({ activities }: { activities: ActivityTemplate[] }) {
  const [editingActivity, setEditingActivity] = useState<ActivityTemplate | null>(null);
  const activateMutation = useActivateActivityTemplate();
  const retireMutation = useRetireActivityTemplate();

  if (activities.length === 0) {
    return (
      <div className="text-center py-12 bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg">
        <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)]" />
        <h3 className="mt-4 text-lg font-medium text-[var(--sl-text-primary)]">
          No activities found
        </h3>
        <p className="mt-2 text-sm text-[var(--sl-text-secondary)]">
          Activities are reusable building blocks for templates
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {activities.map((activity) => (
          <div
            key={activity.id}
            className="bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg p-4 hover:border-[var(--sl-border-hover)] transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-[var(--sl-text-primary)]">
                  {activity.title}
                </h3>
                <p className="text-sm text-[var(--sl-text-secondary)] mt-1 line-clamp-2">
                  {activity.description}
                </p>
              </div>
              <div className="flex items-center gap-2 ml-2">
                <StatusBadge status={activity.status} />
                <SlDropdownMenu>
                  <SlDropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </SlDropdownMenuTrigger>
                  <SlDropdownMenuContent align="end">
                    <SlDropdownMenuItem onClick={() => setEditingActivity(activity)}>
                      <Pencil className="h-4 w-4 mr-2" />
                      Edit
                    </SlDropdownMenuItem>
                    <SlDropdownMenuSeparator />
                    {activity.status === 'draft' && (
                      <SlDropdownMenuItem
                        onClick={() => activateMutation.mutate(activity.id)}
                      >
                        <CheckCircle className="h-4 w-4 mr-2" />
                        Activate
                      </SlDropdownMenuItem>
                    )}
                    {activity.status === 'active' && (
                      <SlDropdownMenuItem
                        onClick={() => retireMutation.mutate(activity.id)}
                        className="text-red-600"
                      >
                        <Archive className="h-4 w-4 mr-2" />
                        Retire
                      </SlDropdownMenuItem>
                    )}
                  </SlDropdownMenuContent>
                </SlDropdownMenu>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <SlBadge variant="outline" className="text-xs">
                {activity.category_code}
              </SlBadge>
              <SlBadge variant="outline" className="text-xs">
                {activity.completion_method}
              </SlBadge>
            </div>
          </div>
        ))}
      </div>

      {/* Edit Activity Dialog */}
      <EditActivityDialog
        activity={editingActivity}
        onOpenChange={(open) => !open && setEditingActivity(null)}
      />
    </>
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

function TemplateListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-[var(--sl-bg-card)] border border-[var(--sl-border)] rounded-lg p-4"
        >
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-4 w-full mt-2" />
          <Skeleton className="h-3 w-48 mt-3" />
        </div>
      ))}
    </div>
  );
}

function CreateTemplateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const createMutation = useCreateInstructionTemplate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = () => {
    createMutation.mutate(
      { title, description },
      {
        onSuccess: (newTemplate) => {
          onOpenChange(false);
          setTitle('');
          setDescription('');
          // Navigate to the detail page to add sections and activities
          navigate({
            to: '/sl/instruction-templates/$templateId',
            params: { templateId: newTemplate.id },
          });
        },
      }
    );
  };

  return (
    <SlDialog open={open} onOpenChange={onOpenChange}>
      <SlDialogContent>
        <SlDialogHeader>
          <SlDialogTitle>Create Instruction Template</SlDialogTitle>
          <SlDialogDescription>
            Create a new template for discharge instructions or care plans
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <SlLabel htmlFor="title">Title</SlLabel>
            <SlInput
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Post-Surgery Recovery Instructions"
            />
          </div>
          <div className="space-y-2">
            <SlLabel htmlFor="description">Description</SlLabel>
            <SlTextarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this template..."
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
            disabled={!title || !description || createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating...' : 'Create Template'}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

// Available data trigger types organized by category
const DATA_TRIGGER_OPTIONS = [
  {
    category: 'Vital Signs',
    options: [
      { value: 'blood_pressure', label: 'Blood Pressure' },
      { value: 'heart_rate', label: 'Heart Rate' },
      { value: 'resting_heart_rate', label: 'Resting Heart Rate' },
      { value: 'spo2', label: 'SpO2 / Oxygen Saturation' },
      { value: 'temperature', label: 'Temperature' },
      { value: 'weight', label: 'Weight' },
      { value: 'blood_glucose', label: 'Blood Glucose' },
    ],
  },
  {
    category: 'Activity & Fitness',
    options: [
      { value: 'steps', label: 'Steps' },
      { value: 'active_minutes', label: 'Active Minutes' },
      { value: 'workout', label: 'Workout / Exercise' },
      { value: 'walking_distance', label: 'Walking Distance' },
    ],
  },
  {
    category: 'Advanced',
    options: [
      { value: 'hrv', label: 'Heart Rate Variability' },
      { value: 'respiratory_rate', label: 'Respiratory Rate' },
      { value: 'questionnaire_response', label: 'Questionnaire Response' },
    ],
  },
];

function CreateActivityDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createMutation = useCreateActivityTemplate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryCode, setCategoryCode] = useState('monitoring');
  const [completionMethod, setCompletionMethod] = useState<'auto' | 'manual' | 'hybrid'>('manual');
  const [selectedTriggers, setSelectedTriggers] = useState<string[]>([]);
  const [confirmationPrompt, setConfirmationPrompt] = useState('');
  const [periodUnit, setPeriodUnit] = useState<'d' | 'wk' | 'mo'>('d');
  const [frequency, setFrequency] = useState('1');
  const [specifyTimes, setSpecifyTimes] = useState(true);
  const [timesOfDay, setTimesOfDay] = useState<string[]>(['08:00']);
  const [selectedDays, setSelectedDays] = useState<string[]>(['mon', 'wed', 'fri']);

  // Update times array when frequency changes
  const handleFrequencyChange = (newFrequency: string) => {
    const newCount = parseInt(newFrequency, 10);
    const currentCount = timesOfDay.length;

    if (newCount > currentCount) {
      // Add default times
      const defaultTimes = ['08:00', '12:00', '16:00', '20:00', '10:00', '14:00', '18:00'];
      const newTimes = [...timesOfDay];
      for (let i = currentCount; i < newCount; i++) {
        newTimes.push(defaultTimes[i] || '12:00');
      }
      setTimesOfDay(newTimes);
    } else if (newCount < currentCount) {
      // Remove excess times
      setTimesOfDay(timesOfDay.slice(0, newCount));
    }
    setFrequency(newFrequency);
  };

  const updateTimeAtIndex = (index: number, value: string) => {
    const newTimes = [...timesOfDay];
    newTimes[index] = value;
    setTimesOfDay(newTimes);
  };

  const showDataTriggers = completionMethod === 'auto' || completionMethod === 'hybrid';
  const showConfirmationPrompt = completionMethod === 'manual' || completionMethod === 'hybrid';

  const toggleTrigger = (value: string) => {
    setSelectedTriggers((prev) =>
      prev.includes(value)
        ? prev.filter((t) => t !== value)
        : [...prev, value]
    );
  };

  const toggleDay = (day: string) => {
    setSelectedDays((prev) =>
      prev.includes(day)
        ? prev.filter((d) => d !== day)
        : [...prev, day]
    );
  };

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setCategoryCode('monitoring');
    setCompletionMethod('manual');
    setSelectedTriggers([]);
    setConfirmationPrompt('');
    setPeriodUnit('d');
    setFrequency('1');
    setSpecifyTimes(true);
    setTimesOfDay(['08:00']);
    setSelectedDays(['mon', 'wed', 'fri']);
  };

  const handleSubmit = () => {
    createMutation.mutate(
      {
        title,
        description,
        category_code: categoryCode,
        completion_method: completionMethod,
        data_trigger_types: showDataTriggers && selectedTriggers.length > 0
          ? selectedTriggers
          : undefined,
        confirmation_prompt: showConfirmationPrompt && confirmationPrompt
          ? confirmationPrompt
          : undefined,
        default_timing: {
          frequency: parseInt(frequency, 10),
          period: 1,
          periodUnit,
          // When specifyTimes is false, send empty array so backend distributes times
          // and large window so patient has flexibility
          timeOfDay: specifyTimes ? timesOfDay.filter(Boolean) : [],
          windowMinutes: specifyTimes ? 60 : 720, // 1 hour vs 12 hours
          dayOfWeek: periodUnit === 'wk' ? selectedDays : undefined,
        },
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          resetForm();
        },
      }
    );
  };

  return (
    <SlDialog open={open} onOpenChange={onOpenChange}>
      <SlDialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <SlDialogHeader>
          <SlDialogTitle>Create Activity Template</SlDialogTitle>
          <SlDialogDescription>
            Activities are reusable building blocks for instruction templates
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-4 py-4">
          {/* Basic Info */}
          <div className="space-y-2">
            <SlLabel htmlFor="activity-title">Title</SlLabel>
            <SlInput
              id="activity-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Daily Blood Pressure Check"
            />
          </div>

          <div className="space-y-2">
            <SlLabel htmlFor="activity-description">Description</SlLabel>
            <SlTextarea
              id="activity-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Instructions for this activity..."
              rows={2}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <SlLabel htmlFor="category">Category</SlLabel>
              <SlSelect value={categoryCode} onValueChange={setCategoryCode}>
                <SlSelectTrigger>
                  <SlSelectValue />
                </SlSelectTrigger>
                <SlSelectContent>
                  <SlSelectItem value="monitoring">Monitoring</SlSelectItem>
                  <SlSelectItem value="medications">Medications</SlSelectItem>
                  <SlSelectItem value="wound-care">Wound Care</SlSelectItem>
                  <SlSelectItem value="activity">Activity & Exercise</SlSelectItem>
                  <SlSelectItem value="diet">Diet & Nutrition</SlSelectItem>
                  <SlSelectItem value="education">Education</SlSelectItem>
                  <SlSelectItem value="follow-up">Follow-up Care</SlSelectItem>
                </SlSelectContent>
              </SlSelect>
            </div>

            <div className="space-y-2">
              <SlLabel htmlFor="completion-method">Completion Method</SlLabel>
              <SlSelect value={completionMethod} onValueChange={(v) => setCompletionMethod(v as 'auto' | 'manual' | 'hybrid')}>
                <SlSelectTrigger>
                  <SlSelectValue />
                </SlSelectTrigger>
                <SlSelectContent>
                  <SlSelectItem value="auto">Auto (from wearable data)</SlSelectItem>
                  <SlSelectItem value="manual">Manual (patient confirms)</SlSelectItem>
                  <SlSelectItem value="hybrid">Hybrid (auto-detect + confirm)</SlSelectItem>
                </SlSelectContent>
              </SlSelect>
            </div>
          </div>

          {/* Conditional: Data Triggers */}
          {showDataTriggers && (
            <div className="space-y-2">
              <SlLabel>
                Data Triggers
                <span className="text-gray-400 font-normal ml-1">(select one or more)</span>
              </SlLabel>
              <div className="border border-gray-300 rounded-md p-3 max-h-48 overflow-y-auto bg-white">
                {DATA_TRIGGER_OPTIONS.map((group) => (
                  <div key={group.category} className="mb-3 last:mb-0">
                    <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                      {group.category}
                    </div>
                    <div className="space-y-1">
                      {group.options.map((option) => (
                        <label
                          key={option.value}
                          className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 px-2 py-1 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedTriggers.includes(option.value)}
                            onChange={() => toggleTrigger(option.value)}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700">{option.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {selectedTriggers.length > 0 && (
                <p className="text-xs text-gray-500">
                  Selected: {selectedTriggers.join(', ')}
                </p>
              )}
            </div>
          )}

          {/* Conditional: Confirmation Prompt */}
          {showConfirmationPrompt && (
            <div className="space-y-2">
              <SlLabel htmlFor="confirmation-prompt">Confirmation Prompt</SlLabel>
              <SlInput
                id="confirmation-prompt"
                value={confirmationPrompt}
                onChange={(e) => setConfirmationPrompt(e.target.value)}
                placeholder="e.g., Did you take your blood pressure reading?"
              />
            </div>
          )}

          {/* Timing Configuration */}
          <div className="border-t pt-4 mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">Default Timing</h4>
            <div className="space-y-4">
              {/* Period and Frequency Row */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <SlLabel htmlFor="period-unit">Frequency Period</SlLabel>
                  <SlSelect value={periodUnit} onValueChange={(v) => setPeriodUnit(v as 'd' | 'wk' | 'mo')}>
                    <SlSelectTrigger>
                      <SlSelectValue />
                    </SlSelectTrigger>
                    <SlSelectContent>
                      <SlSelectItem value="d">Daily</SlSelectItem>
                      <SlSelectItem value="wk">Weekly</SlSelectItem>
                      <SlSelectItem value="mo">Monthly</SlSelectItem>
                    </SlSelectContent>
                  </SlSelect>
                </div>

                <div className="space-y-2">
                  <SlLabel htmlFor="frequency">
                    {periodUnit === 'd' ? 'Times per Day' : periodUnit === 'wk' ? 'Times per Week' : 'Times per Month'}
                  </SlLabel>
                  <SlSelect value={frequency} onValueChange={handleFrequencyChange}>
                    <SlSelectTrigger>
                      <SlSelectValue />
                    </SlSelectTrigger>
                    <SlSelectContent>
                      <SlSelectItem value="1">1 time</SlSelectItem>
                      <SlSelectItem value="2">2 times</SlSelectItem>
                      <SlSelectItem value="3">3 times</SlSelectItem>
                      <SlSelectItem value="4">4 times</SlSelectItem>
                      {periodUnit !== 'd' && <SlSelectItem value="5">5 times</SlSelectItem>}
                      {periodUnit !== 'd' && <SlSelectItem value="6">6 times</SlSelectItem>}
                      {periodUnit === 'wk' && <SlSelectItem value="7">7 times (daily)</SlSelectItem>}
                    </SlSelectContent>
                  </SlSelect>
                </div>
              </div>

              {/* Days of Week for Weekly */}
              {periodUnit === 'wk' && (
                <div className="space-y-2">
                  <SlLabel>Days of Week</SlLabel>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { value: 'mon', label: 'Mon' },
                      { value: 'tue', label: 'Tue' },
                      { value: 'wed', label: 'Wed' },
                      { value: 'thu', label: 'Thu' },
                      { value: 'fri', label: 'Fri' },
                      { value: 'sat', label: 'Sat' },
                      { value: 'sun', label: 'Sun' },
                    ].map((day) => (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => toggleDay(day.value)}
                        className={`px-3 py-1.5 text-sm font-medium rounded-md border transition-colors ${
                          selectedDays.includes(day.value)
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Time Specification Toggle */}
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={specifyTimes}
                      onChange={(e) => setSpecifyTimes(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Specify times</span>
                  </label>
                  {!specifyTimes && (
                    <span className="text-xs text-gray-500">
                      (Patient can complete anytime during the day)
                    </span>
                  )}
                </div>

                {/* Time of Day - only shown when specifyTimes is true */}
                {specifyTimes && (
                  <div className="space-y-2">
                    <SlLabel>
                      {timesOfDay.length === 1 ? 'Time of Day' : 'Times of Day'}
                    </SlLabel>
                    <div className="flex flex-wrap gap-2">
                      {timesOfDay.map((time, index) => (
                        <div key={index} className="flex items-center gap-1">
                          {timesOfDay.length > 1 && (
                            <span className="text-xs text-gray-500 w-4">{index + 1}.</span>
                          )}
                          <input
                            type="time"
                            value={time}
                            onChange={(e) => updateTimeAtIndex(index, e.target.value)}
                            className="h-10 px-3 py-2 text-sm text-gray-900 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!title || !description || createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating...' : 'Create Activity'}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}

function EditActivityDialog({
  activity,
  onOpenChange,
}: {
  activity: ActivityTemplate | null;
  onOpenChange: (open: boolean) => void;
}) {
  const updateMutation = useUpdateActivityTemplate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryCode, setCategoryCode] = useState('monitoring');
  const [completionMethod, setCompletionMethod] = useState<'auto' | 'manual' | 'hybrid'>('manual');
  const [selectedTriggers, setSelectedTriggers] = useState<string[]>([]);
  const [confirmationPrompt, setConfirmationPrompt] = useState('');
  const [periodUnit, setPeriodUnit] = useState<'d' | 'wk' | 'mo'>('d');
  const [frequency, setFrequency] = useState('1');
  const [specifyTimes, setSpecifyTimes] = useState(true);
  const [timesOfDay, setTimesOfDay] = useState<string[]>(['08:00']);
  const [selectedDays, setSelectedDays] = useState<string[]>(['mon', 'wed', 'fri']);

  // Populate form when activity changes
  useEffect(() => {
    if (activity) {
      setTitle(activity.title);
      setDescription(activity.description);
      setCategoryCode(activity.category_code);
      setCompletionMethod(activity.completion_method as 'auto' | 'manual' | 'hybrid');
      setSelectedTriggers(activity.data_trigger_types || []);
      setConfirmationPrompt(activity.confirmation_prompt || '');

      const timing = activity.default_timing || {};
      setPeriodUnit((timing.periodUnit as 'd' | 'wk' | 'mo') || 'd');
      setFrequency(String(timing.frequency || 1));
      const times = timing.timeOfDay || [];
      setSpecifyTimes(times.length > 0);
      setTimesOfDay(times.length > 0 ? times : ['08:00']);
      setSelectedDays(timing.dayOfWeek || ['mon', 'wed', 'fri']);
    }
  }, [activity]);

  const handleFrequencyChange = (newFrequency: string) => {
    const newCount = parseInt(newFrequency, 10);
    const currentCount = timesOfDay.length;

    if (newCount > currentCount) {
      const defaultTimes = ['08:00', '12:00', '16:00', '20:00', '10:00', '14:00', '18:00'];
      const newTimes = [...timesOfDay];
      for (let i = currentCount; i < newCount; i++) {
        newTimes.push(defaultTimes[i] || '12:00');
      }
      setTimesOfDay(newTimes);
    } else if (newCount < currentCount) {
      setTimesOfDay(timesOfDay.slice(0, newCount));
    }
    setFrequency(newFrequency);
  };

  const updateTimeAtIndex = (index: number, value: string) => {
    const newTimes = [...timesOfDay];
    newTimes[index] = value;
    setTimesOfDay(newTimes);
  };

  const showDataTriggers = completionMethod === 'auto' || completionMethod === 'hybrid';
  const showConfirmationPrompt = completionMethod === 'manual' || completionMethod === 'hybrid';

  const toggleTrigger = (value: string) => {
    setSelectedTriggers((prev) =>
      prev.includes(value)
        ? prev.filter((t) => t !== value)
        : [...prev, value]
    );
  };

  const toggleDay = (day: string) => {
    setSelectedDays((prev) =>
      prev.includes(day)
        ? prev.filter((d) => d !== day)
        : [...prev, day]
    );
  };

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setCategoryCode('monitoring');
    setCompletionMethod('manual');
    setSelectedTriggers([]);
    setConfirmationPrompt('');
    setPeriodUnit('d');
    setFrequency('1');
    setSpecifyTimes(true);
    setTimesOfDay(['08:00']);
    setSelectedDays(['mon', 'wed', 'fri']);
  };

  const handleClose = () => {
    resetForm();
    onOpenChange(false);
  };

  const handleSubmit = () => {
    if (!activity) return;

    updateMutation.mutate(
      {
        id: activity.id,
        data: {
          title,
          description,
          category_code: categoryCode,
          completion_method: completionMethod,
          data_trigger_types: showDataTriggers && selectedTriggers.length > 0
            ? selectedTriggers
            : undefined,
          confirmation_prompt: showConfirmationPrompt && confirmationPrompt
            ? confirmationPrompt
            : undefined,
          default_timing: {
            frequency: parseInt(frequency, 10),
            period: 1,
            periodUnit,
            timeOfDay: specifyTimes ? timesOfDay.filter(Boolean) : [],
            windowMinutes: specifyTimes ? 60 : 720,
            dayOfWeek: periodUnit === 'wk' ? selectedDays : undefined,
          },
        },
      },
      {
        onSuccess: () => {
          handleClose();
        },
      }
    );
  };

  return (
    <SlDialog open={!!activity} onOpenChange={(open) => !open && handleClose()}>
      <SlDialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <SlDialogHeader>
          <SlDialogTitle>Edit Activity Template</SlDialogTitle>
          <SlDialogDescription>
            Update the activity template settings
          </SlDialogDescription>
        </SlDialogHeader>

        <div className="space-y-4 py-4">
          {/* Basic Info */}
          <div className="space-y-2">
            <SlLabel htmlFor="edit-activity-title">Title</SlLabel>
            <SlInput
              id="edit-activity-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Daily Blood Pressure Check"
            />
          </div>

          <div className="space-y-2">
            <SlLabel htmlFor="edit-activity-description">Description</SlLabel>
            <SlTextarea
              id="edit-activity-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Instructions for this activity..."
              rows={2}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <SlLabel htmlFor="edit-category">Category</SlLabel>
              <SlSelect value={categoryCode} onValueChange={setCategoryCode}>
                <SlSelectTrigger>
                  <SlSelectValue />
                </SlSelectTrigger>
                <SlSelectContent>
                  <SlSelectItem value="monitoring">Monitoring</SlSelectItem>
                  <SlSelectItem value="medications">Medications</SlSelectItem>
                  <SlSelectItem value="wound-care">Wound Care</SlSelectItem>
                  <SlSelectItem value="activity">Activity & Exercise</SlSelectItem>
                  <SlSelectItem value="diet">Diet & Nutrition</SlSelectItem>
                  <SlSelectItem value="education">Education</SlSelectItem>
                  <SlSelectItem value="follow-up">Follow-up Care</SlSelectItem>
                </SlSelectContent>
              </SlSelect>
            </div>

            <div className="space-y-2">
              <SlLabel htmlFor="edit-completion-method">Completion Method</SlLabel>
              <SlSelect value={completionMethod} onValueChange={(v) => setCompletionMethod(v as 'auto' | 'manual' | 'hybrid')}>
                <SlSelectTrigger>
                  <SlSelectValue />
                </SlSelectTrigger>
                <SlSelectContent>
                  <SlSelectItem value="auto">Auto (from wearable data)</SlSelectItem>
                  <SlSelectItem value="manual">Manual (patient confirms)</SlSelectItem>
                  <SlSelectItem value="hybrid">Hybrid (auto-detect + confirm)</SlSelectItem>
                </SlSelectContent>
              </SlSelect>
            </div>
          </div>

          {/* Conditional: Data Triggers */}
          {showDataTriggers && (
            <div className="space-y-2">
              <SlLabel>
                Data Triggers
                <span className="text-gray-400 font-normal ml-1">(select one or more)</span>
              </SlLabel>
              <div className="border border-gray-300 rounded-md p-3 max-h-48 overflow-y-auto bg-white">
                {DATA_TRIGGER_OPTIONS.map((group) => (
                  <div key={group.category} className="mb-3 last:mb-0">
                    <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                      {group.category}
                    </div>
                    <div className="space-y-1">
                      {group.options.map((option) => (
                        <label
                          key={option.value}
                          className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 px-2 py-1 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedTriggers.includes(option.value)}
                            onChange={() => toggleTrigger(option.value)}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700">{option.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Conditional: Confirmation Prompt */}
          {showConfirmationPrompt && (
            <div className="space-y-2">
              <SlLabel htmlFor="edit-confirmation-prompt">Confirmation Prompt</SlLabel>
              <SlInput
                id="edit-confirmation-prompt"
                value={confirmationPrompt}
                onChange={(e) => setConfirmationPrompt(e.target.value)}
                placeholder="e.g., Did you take your blood pressure reading?"
              />
            </div>
          )}

          {/* Timing Configuration */}
          <div className="border-t pt-4 mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">Default Timing</h4>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <SlLabel htmlFor="edit-period-unit">Frequency Period</SlLabel>
                  <SlSelect value={periodUnit} onValueChange={(v) => setPeriodUnit(v as 'd' | 'wk' | 'mo')}>
                    <SlSelectTrigger>
                      <SlSelectValue />
                    </SlSelectTrigger>
                    <SlSelectContent>
                      <SlSelectItem value="d">Daily</SlSelectItem>
                      <SlSelectItem value="wk">Weekly</SlSelectItem>
                      <SlSelectItem value="mo">Monthly</SlSelectItem>
                    </SlSelectContent>
                  </SlSelect>
                </div>

                <div className="space-y-2">
                  <SlLabel htmlFor="edit-frequency">
                    {periodUnit === 'd' ? 'Times per Day' : periodUnit === 'wk' ? 'Times per Week' : 'Times per Month'}
                  </SlLabel>
                  <SlSelect value={frequency} onValueChange={handleFrequencyChange}>
                    <SlSelectTrigger>
                      <SlSelectValue />
                    </SlSelectTrigger>
                    <SlSelectContent>
                      <SlSelectItem value="1">1 time</SlSelectItem>
                      <SlSelectItem value="2">2 times</SlSelectItem>
                      <SlSelectItem value="3">3 times</SlSelectItem>
                      <SlSelectItem value="4">4 times</SlSelectItem>
                      {periodUnit !== 'd' && <SlSelectItem value="5">5 times</SlSelectItem>}
                      {periodUnit !== 'd' && <SlSelectItem value="6">6 times</SlSelectItem>}
                      {periodUnit === 'wk' && <SlSelectItem value="7">7 times (daily)</SlSelectItem>}
                    </SlSelectContent>
                  </SlSelect>
                </div>
              </div>

              {periodUnit === 'wk' && (
                <div className="space-y-2">
                  <SlLabel>Days of Week</SlLabel>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { value: 'mon', label: 'Mon' },
                      { value: 'tue', label: 'Tue' },
                      { value: 'wed', label: 'Wed' },
                      { value: 'thu', label: 'Thu' },
                      { value: 'fri', label: 'Fri' },
                      { value: 'sat', label: 'Sat' },
                      { value: 'sun', label: 'Sun' },
                    ].map((day) => (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => toggleDay(day.value)}
                        className={`px-3 py-1.5 text-sm font-medium rounded-md border transition-colors ${
                          selectedDays.includes(day.value)
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={specifyTimes}
                      onChange={(e) => setSpecifyTimes(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Specify times</span>
                  </label>
                  {!specifyTimes && (
                    <span className="text-xs text-gray-500">
                      (Patient can complete anytime during the day)
                    </span>
                  )}
                </div>

                {specifyTimes && (
                  <div className="space-y-2">
                    <SlLabel>
                      {timesOfDay.length === 1 ? 'Time of Day' : 'Times of Day'}
                    </SlLabel>
                    <div className="flex flex-wrap gap-2">
                      {timesOfDay.map((time, index) => (
                        <div key={index} className="flex items-center gap-1">
                          {timesOfDay.length > 1 && (
                            <span className="text-xs text-gray-500 w-4">{index + 1}.</span>
                          )}
                          <input
                            type="time"
                            value={time}
                            onChange={(e) => updateTimeAtIndex(index, e.target.value)}
                            className="h-10 px-3 py-2 text-sm text-gray-900 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <SlDialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!title || !description || updateMutation.isPending}
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </Button>
        </SlDialogFooter>
      </SlDialogContent>
    </SlDialog>
  );
}
