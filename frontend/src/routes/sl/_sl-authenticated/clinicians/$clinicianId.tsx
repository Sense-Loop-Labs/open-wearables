/**
 * Sense Loop Clinician Detail Page
 * View and edit clinician information
 */

import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { ArrowLeft, Loader2, User } from 'lucide-react';
import { useEffect, useState } from 'react';

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
  useDeactivateClinician,
  useSlClinician,
  useUpdateClinician,
} from '@/hooks/api/use-sl-clinicians';
import type { ClinicianUpdate, PractitionerWithRoles } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';

export const Route = createFileRoute('/sl/_sl-authenticated/clinicians/$clinicianId')({
  component: SlClinicianDetailPage,
});

function SlClinicianDetailPage() {
  const { clinicianId } = Route.useParams();
  const navigate = useNavigate();
  const { data: clinician, isLoading } = useSlClinician(clinicianId);
  const { mutate: updateClinician, isPending: isUpdating } = useUpdateClinician();
  const { mutate: deactivateClinician, isPending: isDeactivating } = useDeactivateClinician();

  const [formData, setFormData] = useState<ClinicianUpdate>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);

  const organizationId = getSlCurrentOrgId();

  // Initialize form data when clinician loads
  useEffect(() => {
    if (clinician) {
      setFormData({
        first_name: clinician.first_name || '',
        last_name: clinician.last_name || '',
        phone: clinician.phone || '',
        npi_number: clinician.npi_number || '',
        credentials: clinician.credentials || '',
      });
    }
  }, [clinician]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};
    if (!formData.first_name?.trim()) newErrors.first_name = 'First name is required';
    if (!formData.last_name?.trim()) newErrors.last_name = 'Last name is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    if (!organizationId) {
      return;
    }

    updateClinician(
      {
        clinicianId,
        data: {
          first_name: formData.first_name?.trim(),
          last_name: formData.last_name?.trim(),
          phone: formData.phone?.trim() || undefined,
          npi_number: formData.npi_number?.trim() || undefined,
          credentials: formData.credentials?.trim() || undefined,
        },
        organizationId,
      },
      {
        onSuccess: () => {
          navigate({ to: '/sl/clinicians' });
        },
      }
    );
  };

  const handleDeactivate = () => {
    if (!organizationId) return;

    deactivateClinician(
      { clinicianId, organizationId },
      {
        onSuccess: () => {
          setDeactivateDialogOpen(false);
          navigate({ to: '/sl/clinicians' });
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--sl-text-muted)]" />
      </div>
    );
  }

  if (!clinician) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <User className="h-12 w-12 text-[var(--sl-text-muted)]" />
        <p className="text-[var(--sl-text-muted)]">Clinician not found</p>
        <Link to="/sl/clinicians">
          <Button variant="outline" className="border-[var(--sl-border)]">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Clinicians
          </Button>
        </Link>
      </div>
    );
  }

  // Get the clinician's role in the current organization
  const currentOrgRole = clinician.roles?.find(
    (r) => r.organization_id === organizationId && r.is_active
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--sl-text-primary)]">
            Edit Clinician
          </h1>
          <p className="text-sm text-[var(--sl-text-muted)] mt-1">
            {clinician.email}
          </p>
        </div>
        <Link to="/sl/clinicians">
          <Button variant="outline" className="border-[var(--sl-border)] text-[var(--sl-text-secondary)]">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Clinicians
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Edit Form */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="sl-card">
            <div className="sl-card-body space-y-6">
              <h3 className="text-lg font-medium text-[var(--sl-text-primary)]">
                Clinician Information
              </h3>

              {/* Name Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.first_name || ''}
                    onChange={(e) => {
                      setFormData({ ...formData, first_name: e.target.value });
                      if (errors.first_name) setErrors({ ...errors, first_name: '' });
                    }}
                    className="sl-form-input w-full"
                  />
                  {errors.first_name && (
                    <p className="text-xs text-red-500 mt-1">{errors.first_name}</p>
                  )}
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">
                    Last Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.last_name || ''}
                    onChange={(e) => {
                      setFormData({ ...formData, last_name: e.target.value });
                      if (errors.last_name) setErrors({ ...errors, last_name: '' });
                    }}
                    className="sl-form-input w-full"
                  />
                  {errors.last_name && (
                    <p className="text-xs text-red-500 mt-1">{errors.last_name}</p>
                  )}
                </div>
              </div>

              {/* Contact */}
              <div className="sl-form-group">
                <label className="sl-form-label">Phone</label>
                <input
                  type="tel"
                  value={formData.phone || ''}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="sl-form-input w-full"
                  placeholder="(555) 123-4567"
                />
              </div>

              {/* Professional Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">NPI Number</label>
                  <input
                    type="text"
                    value={formData.npi_number || ''}
                    onChange={(e) => setFormData({ ...formData, npi_number: e.target.value })}
                    className="sl-form-input w-full"
                    placeholder="1234567890"
                  />
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">Credentials</label>
                  <input
                    type="text"
                    value={formData.credentials || ''}
                    onChange={(e) => setFormData({ ...formData, credentials: e.target.value })}
                    className="sl-form-input w-full"
                    placeholder="MD, RN, etc."
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-[var(--sl-border)]">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDeactivateDialogOpen(true)}
                  className="border-red-300 text-red-600 hover:bg-red-50"
                >
                  Deactivate Clinician
                </Button>
                <div className="flex items-center gap-3">
                  <Link to="/sl/clinicians">
                    <Button type="button" variant="outline" className="border-[var(--sl-border)]">
                      Cancel
                    </Button>
                  </Link>
                  <Button
                    type="submit"
                    disabled={isUpdating}
                    className="bg-[var(--sl-brand)] hover:bg-[var(--sl-brand-dark)] text-white"
                  >
                    {isUpdating ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save Changes'
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </form>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-6">
          {/* Role Card */}
          <div className="sl-card">
            <div className="sl-card-body">
              <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">
                Role & Status
              </h3>
              <div className="space-y-3">
                <InfoRow label="Email" value={clinician.email} />
                <InfoRow
                  label="Role"
                  value={currentOrgRole?.role_display_name || 'No role'}
                />
                <div className="flex justify-between items-center">
                  <span className="text-sm text-[var(--sl-text-muted)]">Status</span>
                  <StatusBadge isActive={clinician.is_active} />
                </div>
                <InfoRow
                  label="Last Login"
                  value={
                    clinician.last_login_at
                      ? formatDateTime(clinician.last_login_at)
                      : 'Never'
                  }
                />
                <InfoRow
                  label="Created"
                  value={formatDate(clinician.created_at)}
                />
              </div>
            </div>
          </div>

          {/* All Roles */}
          {clinician.roles && clinician.roles.length > 0 && (
            <div className="sl-card">
              <div className="sl-card-body">
                <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">
                  Organization Roles
                </h3>
                <div className="space-y-2">
                  {clinician.roles.map((role) => (
                    <div
                      key={role.id}
                      className="flex items-center justify-between py-2 border-b border-[var(--sl-border)] last:border-0"
                    >
                      <div>
                        <p className="text-sm font-medium text-[var(--sl-text-primary)]">
                          {role.organization_name}
                        </p>
                        <p className="text-xs text-[var(--sl-text-muted)]">
                          {role.role_display_name}
                        </p>
                      </div>
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                          role.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {role.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Deactivate Dialog */}
      <DeactivateDialog
        clinician={clinician}
        open={deactivateDialogOpen}
        onClose={() => setDeactivateDialogOpen(false)}
        onConfirm={handleDeactivate}
        isPending={isDeactivating}
      />
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between">
      <span className="text-sm text-[var(--sl-text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--sl-text-primary)]">
        {value || '-'}
      </span>
    </div>
  );
}

function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
        isActive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
      }`}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

interface DeactivateDialogProps {
  clinician: PractitionerWithRoles;
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
}

function DeactivateDialog({
  clinician,
  open,
  onClose,
  onConfirm,
  isPending,
}: DeactivateDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Deactivate Clinician</DialogTitle>
          <DialogDescription>
            Are you sure you want to deactivate {clinician.first_name} {clinician.last_name}?
            They will no longer be able to access the system.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deactivating...
              </>
            ) : (
              'Deactivate'
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
  return new Date(dateString).toLocaleDateString();
}

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}
