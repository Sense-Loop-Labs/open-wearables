/**
 * Sense Loop Clinicians Page
 * List and manage clinical staff with invite functionality
 */

import { createFileRoute } from '@tanstack/react-router';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  Mail,
  MoreHorizontal,
  Plus,
  Search,
  Shield,
  User,
  UserCog,
  UserMinus,
  UserPlus,
  Users,
} from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import {
  useDeactivateClinician,
  useInviteClinician,
  useSlClinicians,
  useSlRoles,
} from '@/hooks/api/use-sl-clinicians';
import type { PractitionerWithRoles, RoleDefinition } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';

export const Route = createFileRoute('/sl/_sl-authenticated/clinicians/')({
  component: SlCliniciansPage,
});

function SlCliniciansPage() {
  const [search, setSearch] = useState('');
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [deactivateDialog, setDeactivateDialog] = useState<PractitionerWithRoles | null>(null);

  const { data: clinicians, isLoading } = useSlClinicians();
  const { data: roles } = useSlRoles();

  // Filter clinicians based on search
  const filteredClinicians = clinicians?.items?.filter(
    (c) =>
      !search ||
      `${c.first_name} ${c.last_name}`.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase())
  );

  // Get counts
  const activeClinicians = clinicians?.items?.filter((c) => c.is_active)?.length ?? 0;
  const pendingInvites = clinicians?.items?.filter(
    (c) =>
      c.practitioner_roles?.some(
        (r) => r.invited_at && !r.accepted_at
      )
  )?.length ?? 0;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Clinicians</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Manage your clinical team and send invitations
          </p>
        </div>
        <Button
          onClick={() => setInviteDialogOpen(true)}
          className="bg-emerald-600 hover:bg-emerald-700"
        >
          <UserPlus className="h-4 w-4 mr-2" />
          Invite Clinician
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-emerald-500/20 p-2">
              <Users className="h-5 w-5 text-emerald-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{activeClinicians}</p>
              <p className="text-sm text-zinc-400">Active Clinicians</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-yellow-500/20 p-2">
              <Clock className="h-5 w-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{pendingInvites}</p>
              <p className="text-sm text-zinc-400">Pending Invites</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-blue-500/20 p-2">
              <Shield className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{roles?.length ?? 0}</p>
              <p className="text-sm text-zinc-400">Available Roles</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <Input
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
        />
      </div>

      {/* Table */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Clinician</TableHead>
              <TableHead className="text-zinc-400">Role</TableHead>
              <TableHead className="text-zinc-400">Status</TableHead>
              <TableHead className="text-zinc-400">Last Login</TableHead>
              <TableHead className="text-zinc-400 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-zinc-500" />
                </TableCell>
              </TableRow>
            ) : !filteredClinicians?.length ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Users className="h-8 w-8 mx-auto text-zinc-600 mb-2" />
                  <p className="text-zinc-500">
                    {search ? 'No clinicians match your search' : 'No clinicians yet'}
                  </p>
                  {!search && (
                    <Button
                      variant="link"
                      onClick={() => setInviteDialogOpen(true)}
                      className="text-emerald-500 mt-2"
                    >
                      <UserPlus className="h-4 w-4 mr-2" />
                      Invite your first clinician
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              filteredClinicians.map((clinician) => (
                <ClinicianRow
                  key={clinician.id}
                  clinician={clinician}
                  onDeactivate={() => setDeactivateDialog(clinician)}
                />
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Invite Dialog */}
      <InviteClinicianDialog
        open={inviteDialogOpen}
        onClose={() => setInviteDialogOpen(false)}
        roles={roles ?? []}
      />

      {/* Deactivate Dialog */}
      <DeactivateClinicianDialog
        clinician={deactivateDialog}
        onClose={() => setDeactivateDialog(null)}
      />
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

interface ClinicianRowProps {
  clinician: PractitionerWithRoles;
  onDeactivate: () => void;
}

function ClinicianRow({ clinician, onDeactivate }: ClinicianRowProps) {
  const currentOrgId = getSlCurrentOrgId();
  const orgRole = clinician.practitioner_roles?.find(
    (r) => r.organization_id === currentOrgId
  );
  const isPending = orgRole?.invited_at && !orgRole?.accepted_at;

  return (
    <TableRow className="border-zinc-800 hover:bg-zinc-900/50">
      <TableCell>
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-zinc-800 flex items-center justify-center">
            <User className="h-5 w-5 text-zinc-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-white">
              {clinician.first_name} {clinician.last_name}
            </p>
            <p className="text-xs text-zinc-500">{clinician.email}</p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <RoleBadge role={orgRole?.role_definition} />
      </TableCell>
      <TableCell>
        {!clinician.is_active ? (
          <Badge variant="outline" className="text-xs bg-zinc-800 text-zinc-400 border-zinc-700">
            Deactivated
          </Badge>
        ) : isPending ? (
          <Badge variant="outline" className="text-xs bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
            <Clock className="h-3 w-3 mr-1" />
            Pending
          </Badge>
        ) : (
          <Badge variant="outline" className="text-xs bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
            <Check className="h-3 w-3 mr-1" />
            Active
          </Badge>
        )}
      </TableCell>
      <TableCell>
        <span className="text-sm text-zinc-400">
          {clinician.last_login_at
            ? formatDate(clinician.last_login_at)
            : 'Never'}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-zinc-900 border-zinc-800">
            <DropdownMenuItem className="text-zinc-300">
              <UserCog className="h-4 w-4 mr-2" />
              Edit Role
            </DropdownMenuItem>
            {isPending && (
              <DropdownMenuItem className="text-zinc-300">
                <Mail className="h-4 w-4 mr-2" />
                Resend Invite
              </DropdownMenuItem>
            )}
            {clinician.is_active && (
              <DropdownMenuItem
                onClick={onDeactivate}
                className="text-red-400 focus:text-red-400"
              >
                <UserMinus className="h-4 w-4 mr-2" />
                Deactivate
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

function RoleBadge({ role }: { role?: RoleDefinition }) {
  if (!role) {
    return <span className="text-sm text-zinc-500">-</span>;
  }

  const roleColors: Record<string, string> = {
    org_admin: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    doctor: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    physician_assistant: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    nurse_practitioner: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    nurse: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    medical_assistant: 'bg-green-500/20 text-green-400 border-green-500/30',
    care_coordinator: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    readonly: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  };

  return (
    <Badge
      variant="outline"
      className={`text-xs ${roleColors[role.code] || roleColors.readonly}`}
    >
      {role.display_name}
    </Badge>
  );
}

// ============================================================================
// Dialogs
// ============================================================================

interface InviteClinicianDialogProps {
  open: boolean;
  onClose: () => void;
  roles: RoleDefinition[];
}

function InviteClinicianDialog({ open, onClose, roles }: InviteClinicianDialogProps) {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    role: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { mutate: invite, isPending } = useInviteClinician();
  const orgId = getSlCurrentOrgId();

  // Filter to assignable roles (not super_admin)
  const assignableRoles = roles.filter(
    (r) => r.is_active && r.code !== 'super_admin'
  );

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.first_name.trim()) {
      newErrors.first_name = 'First name is required';
    }
    if (!formData.last_name.trim()) {
      newErrors.last_name = 'Last name is required';
    }
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Invalid email address';
    }
    if (!formData.role) {
      newErrors.role = 'Role is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate() || !orgId) return;

    invite(
      {
        organizationId: orgId,
        data: formData,
      },
      {
        onSuccess: () => {
          setFormData({ first_name: '', last_name: '', email: '', role: '' });
          setErrors({});
          onClose();
        },
      }
    );
  };

  const handleClose = () => {
    setFormData({ first_name: '', last_name: '', email: '', role: '' });
    setErrors({});
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Invite Clinician</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Send an invitation email to add a new clinician to your organization.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="first_name" className="text-zinc-300">
                First Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="first_name"
                value={formData.first_name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, first_name: e.target.value }))
                }
                placeholder="John"
                className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
              />
              {errors.first_name && (
                <p className="text-xs text-red-500">{errors.first_name}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="last_name" className="text-zinc-300">
                Last Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="last_name"
                value={formData.last_name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, last_name: e.target.value }))
                }
                placeholder="Smith"
                className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
              />
              {errors.last_name && (
                <p className="text-xs text-red-500">{errors.last_name}</p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email" className="text-zinc-300">
              Email <span className="text-red-500">*</span>
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, email: e.target.value }))
                }
                placeholder="john.smith@hospital.org"
                className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
              />
            </div>
            {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="role" className="text-zinc-300">
              Role <span className="text-red-500">*</span>
            </Label>
            <Select
              value={formData.role}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, role: v }))
              }
            >
              <SelectTrigger className="bg-zinc-900 border-zinc-700 text-white">
                <SelectValue placeholder="Select a role" />
              </SelectTrigger>
              <SelectContent>
                {assignableRoles.map((role) => (
                  <SelectItem key={role.id} value={role.code}>
                    <div className="flex items-center gap-2">
                      <span>{role.display_name}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.role && <p className="text-xs text-red-500">{errors.role}</p>}
          </div>

          {/* Role permissions preview */}
          {formData.role && (
            <RolePermissionsPreview
              role={assignableRoles.find((r) => r.code === formData.role)}
            />
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isPending}
            className="border-zinc-700"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Mail className="mr-2 h-4 w-4" />
                Send Invitation
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RolePermissionsPreview({ role }: { role?: RoleDefinition }) {
  if (!role) return null;

  const permissions = [
    { key: 'can_manage_patients', label: 'Manage Patients', value: role.can_manage_patients },
    { key: 'can_manage_alerts', label: 'Manage Alerts', value: role.can_manage_alerts },
    { key: 'can_resolve_alerts', label: 'Resolve Alerts', value: role.can_resolve_alerts },
    { key: 'can_acknowledge_alerts', label: 'Acknowledge Alerts', value: role.can_acknowledge_alerts },
    { key: 'can_manage_care_plans', label: 'Manage Care Plans', value: role.can_manage_care_plans },
    { key: 'can_manage_clinicians', label: 'Manage Clinicians', value: role.can_manage_clinicians },
    { key: 'can_manage_org_settings', label: 'Manage Settings', value: role.can_manage_org_settings },
    { key: 'can_view_audit_logs', label: 'View Audit Logs', value: role.can_view_audit_logs },
  ];

  return (
    <div className="rounded-lg bg-zinc-900 p-4">
      <p className="text-sm font-medium text-zinc-300 mb-3">Role Permissions</p>
      <div className="grid grid-cols-2 gap-2">
        {permissions.map((perm) => (
          <div key={perm.key} className="flex items-center gap-2">
            {perm.value ? (
              <Check className="h-4 w-4 text-emerald-500" />
            ) : (
              <span className="h-4 w-4 text-zinc-600">-</span>
            )}
            <span
              className={`text-xs ${perm.value ? 'text-zinc-300' : 'text-zinc-500'}`}
            >
              {perm.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface DeactivateClinicianDialogProps {
  clinician: PractitionerWithRoles | null;
  onClose: () => void;
}

function DeactivateClinicianDialog({
  clinician,
  onClose,
}: DeactivateClinicianDialogProps) {
  const { mutate: deactivate, isPending } = useDeactivateClinician();

  const handleDeactivate = () => {
    if (!clinician) return;

    deactivate(clinician.id, {
      onSuccess: () => {
        onClose();
      },
    });
  };

  return (
    <Dialog open={!!clinician} onOpenChange={() => onClose()}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            Deactivate Clinician
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            This will remove the clinician's access to this organization.
          </DialogDescription>
        </DialogHeader>

        {clinician && (
          <div className="py-4">
            <div className="rounded-lg bg-zinc-900 p-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-zinc-800 flex items-center justify-center">
                  <User className="h-5 w-5 text-zinc-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">
                    {clinician.first_name} {clinician.last_name}
                  </p>
                  <p className="text-xs text-zinc-500">{clinician.email}</p>
                </div>
              </div>
            </div>
            <p className="text-sm text-zinc-400 mt-4">
              The clinician will no longer be able to access patient data or manage
              alerts. This action can be reversed by an organization admin.
            </p>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isPending}
            className="border-zinc-700"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDeactivate}
            disabled={isPending}
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deactivating...
              </>
            ) : (
              <>
                <UserMinus className="mr-2 h-4 w-4" />
                Deactivate
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return 'Today';
  } else if (diffDays === 1) {
    return 'Yesterday';
  } else if (diffDays < 7) {
    return `${diffDays} days ago`;
  }

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}
