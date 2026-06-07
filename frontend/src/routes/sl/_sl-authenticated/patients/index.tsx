/**
 * Sense Loop Patients List Page
 */

import { createFileRoute, Link, useSearch } from '@tanstack/react-router';
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Plus,
  Search,
  Users,
} from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useCreateSlPatient, useSlPatients } from '@/hooks/api/use-sl-patients';
import { useSurgeryTypes } from '@/hooks/api/use-sl-value-sets';
import type { PatientCreate, PatientEnrollmentStatus } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';

interface SearchParams {
  page?: number;
  search?: string;
  status?: PatientEnrollmentStatus;
}

export const Route = createFileRoute('/sl/_sl-authenticated/patients/')({
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    page: Number(search.page) || 1,
    search: (search.search as string) || undefined,
    status: search.status as PatientEnrollmentStatus | undefined,
  }),
  component: SlPatientsPage,
});

function SlPatientsPage() {
  const search = useSearch({ from: '/sl/_sl-authenticated/patients/' });
  const [searchInput, setSearchInput] = useState(search.search || '');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const { data, isLoading } = useSlPatients({
    page: search.page,
    search: search.search,
    enrollment_status: search.status,
    page_size: 20,
  });

  const patients = data?.items ?? [];
  const totalPages = data?.pages ?? 1;
  const currentPage = data?.page ?? 1;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Patients</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Manage and monitor patient status
          </p>
        </div>
        <Button
          onClick={() => setCreateDialogOpen(true)}
          className="bg-emerald-600 hover:bg-emerald-700"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Patient
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <Input
            placeholder="Search patients..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                // Navigate with search param
                window.location.href = `/sl/patients?search=${encodeURIComponent(searchInput)}`;
              }
            }}
            className="pl-10 bg-zinc-900 border-zinc-700"
          />
        </div>

        <Select
          value={search.status || 'all'}
          onValueChange={(value) => {
            const status = value === 'all' ? '' : value;
            window.location.href = `/sl/patients?status=${status}`;
          }}
        >
          <SelectTrigger className="w-[180px] bg-zinc-900 border-zinc-700">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="activated">Activated</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="discharged">Discharged</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
          </div>
        ) : patients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="rounded-full bg-zinc-800 p-4 mb-4">
              <Users className="h-8 w-8 text-zinc-500" />
            </div>
            <p className="text-lg font-medium text-white">No patients found</p>
            <p className="text-sm text-zinc-500 mt-1">
              {search.search
                ? 'Try adjusting your search terms'
                : 'Add your first patient to get started'}
            </p>
            <Button
              onClick={() => setCreateDialogOpen(true)}
              className="mt-4 bg-emerald-600 hover:bg-emerald-700"
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Patient
            </Button>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow className="border-zinc-800 hover:bg-transparent">
                  <TableHead className="text-zinc-400">Patient</TableHead>
                  <TableHead className="text-zinc-400">MRN</TableHead>
                  <TableHead className="text-zinc-400">Status</TableHead>
                  <TableHead className="text-zinc-400">Day</TableHead>
                  <TableHead className="text-zinc-400">Vitals</TableHead>
                  <TableHead className="text-zinc-400">Alerts</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {patients.map((patient) => (
                  <TableRow
                    key={patient.id}
                    className="border-zinc-800 hover:bg-zinc-900 cursor-pointer"
                  >
                    <TableCell>
                      <Link
                        to="/sl/patients/$patientId"
                        params={{ patientId: patient.id }}
                        className="block"
                      >
                        <p className="font-medium text-white">{patient.full_name}</p>
                        <p className="text-xs text-zinc-500">{patient.email || 'No email'}</p>
                      </Link>
                    </TableCell>
                    <TableCell className="text-zinc-400">
                      {patient.mrn || '-'}
                    </TableCell>
                    <TableCell>
                      <EnrollmentBadge status={patient.enrollment_status} />
                    </TableCell>
                    <TableCell className="text-zinc-400">
                      {patient.days_post_surgery !== null
                        ? `Day ${patient.days_post_surgery}`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {patient.summary ? (
                        <VitalsPreview summary={patient.summary} />
                      ) : (
                        <span className="text-zinc-500">No data</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <AlertsBadges
                        critical={patient.summary?.active_critical_alerts_count ?? 0}
                        warning={(patient.summary?.active_alerts_count ?? 0) - (patient.summary?.active_critical_alerts_count ?? 0)}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800">
              <p className="text-sm text-zinc-500">
                Page {currentPage} of {totalPages} ({data?.total ?? 0} patients)
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage <= 1}
                  onClick={() => {
                    window.location.href = `/sl/patients?page=${currentPage - 1}`;
                  }}
                  className="border-zinc-700"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage >= totalPages}
                  onClick={() => {
                    window.location.href = `/sl/patients?page=${currentPage + 1}`;
                  }}
                  className="border-zinc-700"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Create Patient Dialog */}
      <CreatePatientDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

function EnrollmentBadge({ status }: { status: PatientEnrollmentStatus }) {
  const variants: Record<PatientEnrollmentStatus, { color: string; label: string }> = {
    pending: { color: 'bg-zinc-700 text-zinc-300', label: 'Pending' },
    activated: { color: 'bg-blue-900 text-blue-300', label: 'Activated' },
    active: { color: 'bg-emerald-900 text-emerald-300', label: 'Active' },
    discharged: { color: 'bg-purple-900 text-purple-300', label: 'Discharged' },
    inactive: { color: 'bg-zinc-800 text-zinc-500', label: 'Inactive' },
  };

  const { color, label } = variants[status] || variants.pending;

  return <Badge className={`${color} text-xs`}>{label}</Badge>;
}

function VitalsPreview({ summary }: { summary: { latest_heart_rate?: number | null; latest_spo2?: number | null } }) {
  return (
    <div className="flex items-center gap-3 text-xs">
      {summary.latest_heart_rate !== null && summary.latest_heart_rate !== undefined && (
        <span className="text-zinc-400">
          HR: <span className="text-white">{summary.latest_heart_rate}</span>
        </span>
      )}
      {summary.latest_spo2 !== null && summary.latest_spo2 !== undefined && (
        <span className="text-zinc-400">
          SpO2: <span className="text-white">{summary.latest_spo2}%</span>
        </span>
      )}
      {!summary.latest_heart_rate && !summary.latest_spo2 && (
        <span className="text-zinc-500">No vitals</span>
      )}
    </div>
  );
}

function AlertsBadges({ critical, warning }: { critical: number; warning: number }) {
  if (critical === 0 && warning === 0) {
    return <span className="text-zinc-500 text-sm">None</span>;
  }

  return (
    <div className="flex items-center gap-1">
      {critical > 0 && (
        <Badge variant="destructive" className="text-xs">
          {critical}
        </Badge>
      )}
      {warning > 0 && (
        <Badge variant="outline" className="text-xs border-yellow-600 text-yellow-500">
          {warning}
        </Badge>
      )}
    </div>
  );
}

function CreatePatientDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createPatient = useCreateSlPatient();
  const { data: surgeryTypes, isLoading: surgeryTypesLoading } = useSurgeryTypes();
  const [formData, setFormData] = useState<Partial<PatientCreate>>({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    mrn: '',
    date_of_birth: '',
    gender: '',
    primary_diagnosis: '',
    surgery_type_code: '',
    surgery_date: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};
    if (!formData.first_name?.trim()) newErrors.first_name = 'First name is required';
    if (!formData.last_name?.trim()) newErrors.last_name = 'Last name is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const orgId = getSlCurrentOrgId();
    if (!orgId) {
      setErrors({ general: 'No organization selected' });
      return;
    }

    try {
      await createPatient.mutateAsync({
        organization_id: orgId,
        first_name: formData.first_name!.trim(),
        last_name: formData.last_name!.trim(),
        email: formData.email?.trim() || undefined,
        phone: formData.phone?.trim() || undefined,
        mrn: formData.mrn?.trim() || undefined,
        date_of_birth: formData.date_of_birth || undefined,
        gender: formData.gender || undefined,
        primary_diagnosis: formData.primary_diagnosis?.trim() || undefined,
        surgery_type_code: formData.surgery_type_code || undefined,
        surgery_date: formData.surgery_date || undefined,
      });

      onOpenChange(false);
      setFormData({});
      setErrors({});
    } catch {
      // Error handled by hook
    }
  };

  const handleClose = () => {
    onOpenChange(false);
    setFormData({});
    setErrors({});
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white max-w-lg">
        <DialogHeader>
          <DialogTitle>Add New Patient</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">
                First Name <span className="text-red-500">*</span>
              </label>
              <Input
                value={formData.first_name || ''}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
              {errors.first_name && (
                <p className="text-xs text-red-500">{errors.first_name}</p>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">
                Last Name <span className="text-red-500">*</span>
              </label>
              <Input
                value={formData.last_name || ''}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
              {errors.last_name && (
                <p className="text-xs text-red-500">{errors.last_name}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Email</label>
              <Input
                type="email"
                value={formData.email || ''}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Phone</label>
              <Input
                value={formData.phone || ''}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">MRN</label>
              <Input
                value={formData.mrn || ''}
                onChange={(e) => setFormData({ ...formData, mrn: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Date of Birth</label>
              <Input
                type="date"
                value={formData.date_of_birth || ''}
                onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Gender</label>
              <Select
                value={formData.gender || ''}
                onValueChange={(value) => setFormData({ ...formData, gender: value })}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700">
                  <SelectValue placeholder="Select gender" />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  <SelectItem value="male">Male</SelectItem>
                  <SelectItem value="female">Female</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Surgery Type</label>
              <Select
                value={formData.surgery_type_code || ''}
                onValueChange={(value) => setFormData({ ...formData, surgery_type_code: value })}
                disabled={surgeryTypesLoading}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700">
                  <SelectValue placeholder={surgeryTypesLoading ? 'Loading...' : 'Select surgery type'} />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  {surgeryTypes?.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Surgery Date</label>
              <Input
                type="date"
                value={formData.surgery_date || ''}
                onChange={(e) => setFormData({ ...formData, surgery_date: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Primary Diagnosis</label>
              <Input
                value={formData.primary_diagnosis || ''}
                onChange={(e) => setFormData({ ...formData, primary_diagnosis: e.target.value })}
                className="bg-zinc-900 border-zinc-700"
                placeholder="e.g., PAD"
              />
            </div>
          </div>

          {errors.general && (
            <p className="text-sm text-red-500">{errors.general}</p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              className="border-zinc-700"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700"
              disabled={createPatient.isPending}
            >
              {createPatient.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Patient'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
