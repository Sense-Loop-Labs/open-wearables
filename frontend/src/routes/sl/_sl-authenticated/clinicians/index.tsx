/**
 * Sense Loop Clinicians Page
 * List and manage clinical staff with invite functionality
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  AlertTriangle,
  Check,
  Clock,
  Loader2,
  Mail,
  MoreHorizontal,
  Search,
  Shield,
  User,
  UserCog,
  UserMinus,
  UserPlus,
  Users,
} from 'lucide-react';
import { useEffect, useState } from 'react';

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
  parseValidationErrors,
  useDeactivateClinician,
  useInviteClinician,
  useResendInvite,
  useRevokeInvite,
  useSlClinicians,
  useSlPendingInvites,
  useSlRoles,
} from '@/hooks/api/use-sl-clinicians';
import type { PractitionerInvite, PractitionerWithRoles, RoleDefinition } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId, getSlCurrentPractitioner } from '@/lib/auth/sl-session';

export const Route = createFileRoute('/sl/_sl-authenticated/clinicians/')({
  component: SlCliniciansPage,
});

function SlCliniciansPage() {
  const [search, setSearch] = useState('');
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [deactivateDialog, setDeactivateDialog] = useState<PractitionerWithRoles | null>(null);

  const { data: clinicians, isLoading } = useSlClinicians();
  const { data: pendingInvites, isLoading: isLoadingInvites } = useSlPendingInvites();
  const { data: roles } = useSlRoles();

  // Get current user's privilege level
  const currentPractitioner = getSlCurrentPractitioner();
  const currentUserRoleCode = currentPractitioner?.currentOrg?.role;
  const currentUserPrivilegeLevel = roles?.find(r => r.code === currentUserRoleCode)?.privilege_level ?? 0;

  // Filter clinicians based on search
  const filteredClinicians = clinicians?.items?.filter(
    (c) =>
      !search ||
      `${c.first_name} ${c.last_name}`.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase())
  );

  // Filter pending invites based on search
  const filteredInvites = pendingInvites?.filter(
    (inv) =>
      !search ||
      `${inv.first_name} ${inv.last_name}`.toLowerCase().includes(search.toLowerCase()) ||
      inv.email.toLowerCase().includes(search.toLowerCase())
  );

  // Get counts
  const activeClinicians = clinicians?.items?.filter((c) => c.is_active)?.length ?? 0;
  const pendingInviteCount = pendingInvites?.length ?? 0;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--sl-text-primary)]">Clinicians</h1>
          <p className="text-sm text-[var(--sl-text-muted)] mt-1">
            Manage your clinical team and send invitations
          </p>
        </div>
        <Button
          onClick={() => setInviteDialogOpen(true)}
        >
          <UserPlus className="h-4 w-4 mr-2" />
          Invite Clinician
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-[var(--sl-border)] bg-[var(--sl-bg-card)] p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-emerald-500/20 p-2">
              <Users className="h-5 w-5 text-emerald-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--sl-text-primary)]">{activeClinicians}</p>
              <p className="text-sm text-[var(--sl-text-muted)]">Active Clinicians</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-[var(--sl-border)] bg-[var(--sl-bg-card)] p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-yellow-500/20 p-2">
              <Clock className="h-5 w-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--sl-text-primary)]">{pendingInviteCount}</p>
              <p className="text-sm text-[var(--sl-text-muted)]">Pending Invites</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-[var(--sl-border)] bg-[var(--sl-bg-card)] p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-blue-500/20 p-2">
              <Shield className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--sl-text-primary)]">{roles?.length ?? 0}</p>
              <p className="text-sm text-[var(--sl-text-muted)]">Available Roles</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--sl-text-muted)]" />
        <Input
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 sl-form-input"
        />
      </div>

      {/* Table */}
      <div className="rounded-xl border border-[var(--sl-border)] bg-[var(--sl-bg-card)] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[var(--sl-border)] hover:bg-transparent">
              <TableHead className="text-[var(--sl-text-muted)]">Clinician</TableHead>
              <TableHead className="text-[var(--sl-text-muted)]">Role</TableHead>
              <TableHead className="text-[var(--sl-text-muted)]">Status</TableHead>
              <TableHead className="text-[var(--sl-text-muted)]">Last Login</TableHead>
              <TableHead className="text-[var(--sl-text-muted)] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading || isLoadingInvites ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-[var(--sl-text-muted)]" />
                </TableCell>
              </TableRow>
            ) : !filteredClinicians?.length && !filteredInvites?.length ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Users className="h-8 w-8 mx-auto text-[var(--sl-text-muted)] mb-2" />
                  <p className="text-[var(--sl-text-muted)]">
                    {search ? 'No clinicians match your search' : 'No clinicians yet'}
                  </p>
                  {!search && (
                    <Button
                      variant="link"
                      onClick={() => setInviteDialogOpen(true)}
                      className="text-[var(--sl-brand)] mt-2"
                    >
                      <UserPlus className="h-4 w-4 mr-2" />
                      Invite your first clinician
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              <>
                {/* Pending invites first */}
                {filteredInvites?.map((invite) => (
                  <PendingInviteRow key={invite.id} invite={invite} roles={roles ?? []} />
                ))}
                {/* Active clinicians */}
                {filteredClinicians?.map((clinician) => (
                  <ClinicianRow
                    key={clinician.id}
                    clinician={clinician}
                    onDeactivate={() => setDeactivateDialog(clinician)}
                    currentUserPrivilegeLevel={currentUserPrivilegeLevel}
                    roles={roles ?? []}
                  />
                ))}
              </>
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
  currentUserPrivilegeLevel: number;
  roles: RoleDefinition[];
}

function ClinicianRow({ clinician, onDeactivate, currentUserPrivilegeLevel, roles }: ClinicianRowProps) {
  const currentOrgId = getSlCurrentOrgId();
  const orgRole = clinician.roles?.find(
    (r) => r.organization_id === currentOrgId
  );

  // Check if current user can manage this clinician (must have >= privilege level)
  const clinicianPrivilegeLevel = roles.find(r => r.code === orgRole?.role_code)?.privilege_level ?? 0;
  const canManage = currentUserPrivilegeLevel >= clinicianPrivilegeLevel;

  return (
    <TableRow className="border-[var(--sl-border)] hover:bg-[var(--sl-bg-muted)]">
      <TableCell>
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-[var(--sl-bg-muted)] flex items-center justify-center">
            <User className="h-5 w-5 text-[var(--sl-text-muted)]" />
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--sl-text-primary)]">
              {clinician.first_name} {clinician.last_name}
            </p>
            <p className="text-xs text-[var(--sl-text-muted)]">{clinician.email}</p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <RoleBadgeFromCode code={orgRole?.role_code} displayName={orgRole?.role_display_name} />
      </TableCell>
      <TableCell>
        {!clinician.is_active ? (
          <Badge variant="outline" className="text-xs bg-gray-100 text-gray-500 border-gray-300">
            Deactivated
          </Badge>
        ) : (
          <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-600 border-emerald-300">
            <Check className="h-3 w-3 mr-1" />
            Active
          </Badge>
        )}
      </TableCell>
      <TableCell>
        <span className="text-sm text-[var(--sl-text-muted)]">
          {clinician.last_login_at
            ? formatDate(clinician.last_login_at)
            : 'Never'}
        </span>
      </TableCell>
      <TableCell className="text-right">
        {canManage ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-white border-[var(--sl-border)]">
              <DropdownMenuItem asChild className="text-[var(--sl-text-secondary)]">
                <Link to="/sl/clinicians/$clinicianId" params={{ clinicianId: clinician.id }}>
                  <UserCog className="h-4 w-4 mr-2" />
                  Edit
                </Link>
              </DropdownMenuItem>
              {clinician.is_active && (
                <DropdownMenuItem
                  onClick={onDeactivate}
                  className="text-red-600 focus:text-red-600"
                >
                  <UserMinus className="h-4 w-4 mr-2" />
                  Deactivate
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <span className="text-xs text-[var(--sl-text-muted)]">-</span>
        )}
      </TableCell>
    </TableRow>
  );
}

interface PendingInviteRowProps {
  invite: PractitionerInvite;
  roles: RoleDefinition[];
}

function PendingInviteRow({ invite, roles }: PendingInviteRowProps) {
  const role = roles.find((r) => r.code === invite.role_code);
  const { mutate: resendInvite, isPending: isResending } = useResendInvite();
  const { mutate: revokeInvite, isPending: isRevoking } = useRevokeInvite();

  const handleResend = () => {
    resendInvite(invite.id);
  };

  const handleRevoke = () => {
    revokeInvite(invite.id);
  };

  return (
    <TableRow className="border-[var(--sl-border)] hover:bg-[var(--sl-bg-muted)] bg-yellow-50/30">
      <TableCell>
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-yellow-100 flex items-center justify-center">
            <Mail className="h-5 w-5 text-yellow-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--sl-text-primary)]">
              {invite.first_name} {invite.last_name}
            </p>
            <p className="text-xs text-[var(--sl-text-muted)]">{invite.email}</p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <RoleBadge role={role} />
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs bg-yellow-50 text-yellow-600 border-yellow-300">
          <Clock className="h-3 w-3 mr-1" />
          Pending Invite
        </Badge>
      </TableCell>
      <TableCell>
        <span className={`text-sm ${invite.is_expired ? 'text-red-500' : 'text-[var(--sl-text-muted)]'}`}>
          {formatExpirationDate(invite.expires_at)}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" disabled={isResending || isRevoking}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-white border-[var(--sl-border)]">
            <DropdownMenuItem
              onClick={handleResend}
              disabled={isResending}
              className="text-[var(--sl-text-secondary)]"
            >
              <Mail className="h-4 w-4 mr-2" />
              {isResending ? 'Resending...' : 'Resend Invite'}
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleRevoke}
              disabled={isRevoking}
              className="text-red-600 focus:text-red-600"
            >
              <UserMinus className="h-4 w-4 mr-2" />
              {isRevoking ? 'Revoking...' : 'Revoke Invite'}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

function RoleBadge({ role }: { role?: RoleDefinition }) {
  if (!role) {
    return <span className="text-sm text-[var(--sl-text-muted)]">-</span>;
  }

  return <RoleBadgeFromCode code={role.code} displayName={role.display_name} />;
}

function RoleBadgeFromCode({ code, displayName }: { code?: string; displayName?: string }) {
  if (!code || !displayName) {
    return <span className="text-sm text-[var(--sl-text-muted)]">-</span>;
  }

  const roleColors: Record<string, string> = {
    org_admin: 'bg-purple-50 text-purple-600 border-purple-300',
    doctor: 'bg-blue-50 text-blue-600 border-blue-300',
    physician: 'bg-blue-50 text-blue-600 border-blue-300',
    physician_assistant: 'bg-cyan-50 text-cyan-600 border-cyan-300',
    nurse_practitioner: 'bg-cyan-50 text-cyan-600 border-cyan-300',
    nurse: 'bg-emerald-50 text-emerald-600 border-emerald-300',
    medical_assistant: 'bg-green-50 text-green-600 border-green-300',
    care_coordinator: 'bg-amber-50 text-amber-600 border-amber-300',
    readonly: 'bg-gray-50 text-gray-600 border-gray-300',
  };

  return (
    <Badge
      variant="outline"
      className={`text-xs ${roleColors[code] || roleColors.readonly}`}
    >
      {displayName}
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
    role_code: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { mutate: invite, isPending, error: mutationError, reset } = useInviteClinician();
  const orgId = getSlCurrentOrgId();

  // Handle mutation errors - parse field-level validation errors
  useEffect(() => {
    if (mutationError) {
      const fieldErrors = parseValidationErrors(mutationError);
      if (fieldErrors) {
        setErrors(fieldErrors);
      } else {
        // Show general error if not field-specific
        setErrors({ _form: mutationError.message || 'Failed to send invitation' });
      }
    }
  }, [mutationError]);

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
    if (!formData.role_code) {
      newErrors.role_code = 'Role is required';
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
          setFormData({ first_name: '', last_name: '', email: '', role_code: '' });
          setErrors({});
          reset();
          onClose();
        },
      }
    );
  };

  const handleClose = () => {
    setFormData({ first_name: '', last_name: '', email: '', role_code: '' });
    setErrors({});
    reset();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite Clinician</DialogTitle>
          <DialogDescription>
            Send an invitation email to add a new clinician to your organization.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="first_name" className="text-[var(--sl-text-secondary)]">
                First Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="first_name"
                value={formData.first_name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, first_name: e.target.value }))
                }
                placeholder="John"
                className="sl-form-input"
              />
              {errors.first_name && (
                <p className="text-xs text-red-500">{errors.first_name}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="last_name" className="text-[var(--sl-text-secondary)]">
                Last Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="last_name"
                value={formData.last_name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, last_name: e.target.value }))
                }
                placeholder="Smith"
                className="sl-form-input"
              />
              {errors.last_name && (
                <p className="text-xs text-red-500">{errors.last_name}</p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email" className="text-[var(--sl-text-secondary)]">
              Email <span className="text-red-500">*</span>
            </Label>
            <Input
              id="email"
              type="email"
              value={formData.email}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, email: e.target.value }))
              }
              placeholder="john.smith@hospital.org"
              className="sl-form-input"
            />
            {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="role" className="text-[var(--sl-text-secondary)]">
              Role <span className="text-red-500">*</span>
            </Label>
            <Select
              value={formData.role_code}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, role_code: v }))
              }
            >
              <SelectTrigger className="sl-form-input">
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
            {errors.role_code && <p className="text-xs text-red-500">{errors.role_code}</p>}
          </div>

          {/* Role permissions preview */}
          {formData.role_code && (
            <RolePermissionsPreview
              role={assignableRoles.find((r) => r.code === formData.role_code)}
            />
          )}

          {/* General form error */}
          {errors._form && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3">
              <p className="text-sm text-red-600">{errors._form}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending}
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
    <div className="rounded-lg bg-[var(--sl-bg-muted)] border border-[var(--sl-border)] p-4">
      <p className="text-sm font-medium text-[var(--sl-text-secondary)] mb-3">Role Permissions</p>
      <div className="grid grid-cols-2 gap-2">
        {permissions.map((perm) => (
          <div key={perm.key} className="flex items-center gap-2">
            {perm.value ? (
              <Check className="h-4 w-4 text-emerald-500" />
            ) : (
              <span className="h-4 w-4 text-[var(--sl-text-muted)]">-</span>
            )}
            <span
              className={`text-xs ${perm.value ? 'text-[var(--sl-text-secondary)]' : 'text-[var(--sl-text-muted)]'}`}
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
  const organizationId = getSlCurrentOrgId();

  const handleDeactivate = () => {
    if (!clinician || !organizationId) return;

    deactivate(
      { clinicianId: clinician.id, organizationId },
      {
        onSuccess: () => {
          onClose();
        },
      }
    );
  };

  return (
    <Dialog open={!!clinician} onOpenChange={() => onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            Deactivate Clinician
          </DialogTitle>
          <DialogDescription>
            This will remove the clinician's access to this organization.
          </DialogDescription>
        </DialogHeader>

        {clinician && (
          <div className="py-4">
            <div className="rounded-lg bg-[var(--sl-bg-muted)] border border-[var(--sl-border)] p-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-[var(--sl-bg-hover)] flex items-center justify-center">
                  <User className="h-5 w-5 text-[var(--sl-text-muted)]" />
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--sl-text-primary)]">
                    {clinician.first_name} {clinician.last_name}
                  </p>
                  <p className="text-xs text-[var(--sl-text-muted)]">{clinician.email}</p>
                </div>
              </div>
            </div>
            <p className="text-sm text-[var(--sl-text-muted)] mt-4">
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

function formatExpirationDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMs < 0) {
    return 'Expired';
  } else if (diffHours < 1) {
    return 'Expires soon';
  } else if (diffHours < 24) {
    return `Expires in ${diffHours} hour${diffHours === 1 ? '' : 's'}`;
  } else if (diffDays === 1) {
    return 'Expires tomorrow';
  } else {
    return `Expires in ${diffDays} days`;
  }
}
