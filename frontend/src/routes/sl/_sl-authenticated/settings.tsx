/**
 * Sense Loop Settings Page
 * Organization settings for notifications and alerts
 */

import { createFileRoute } from '@tanstack/react-router';
import { Bell, AlertTriangle, Save, Loader2, Shield } from 'lucide-react';
import { useState, useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useSlSettings, useUpdateSlSettings } from '@/hooks/api/use-sl-settings';
import { getSlCurrentOrgId, getSlCurrentPractitioner } from '@/lib/auth/sl-session';
import type { NotificationSettings, AlertSettings } from '@/lib/api/types/sense-loop';

export const Route = createFileRoute('/sl/_sl-authenticated/settings')({
  component: SlSettingsPage,
});

// Default values matching backend DEFAULTS
const DEFAULT_NOTIFICATIONS: NotificationSettings = {
  enabled: true,
  patient_reminder_channel: 'push',
  care_team_alert_channel: 'email',
  quiet_hours_enabled: false,
  quiet_hours_start: null,
  quiet_hours_end: null,
};

const DEFAULT_ALERTS: AlertSettings = {
  auto_escalate: false,
  escalation_delay_minutes: 60,
};

function SlSettingsPage() {
  const { data: settings, isLoading, error } = useSlSettings();
  const { mutate: updateSettings, isPending: isSaving } = useUpdateSlSettings();

  // Local state for form - start with defaults
  const [notifications, setNotifications] = useState<NotificationSettings>(DEFAULT_NOTIFICATIONS);
  const [alerts, setAlerts] = useState<AlertSettings>(DEFAULT_ALERTS);
  const [hasChanges, setHasChanges] = useState(false);

  // Update form when settings load
  useEffect(() => {
    if (settings) {
      setNotifications({
        ...DEFAULT_NOTIFICATIONS,
        ...settings.notifications,
      });
      setAlerts({
        ...DEFAULT_ALERTS,
        ...settings.alerts,
      });
      setHasChanges(false);
    }
  }, [settings]);

  // Check if user has permission (org_admin or super_admin can manage settings)
  const currentPractitioner = getSlCurrentPractitioner();
  const hasPermission = currentPractitioner?.currentOrg?.role === 'org_admin' ||
                        currentPractitioner?.currentOrg?.role === 'super_admin';

  const handleNotificationChange = <K extends keyof NotificationSettings>(
    key: K,
    value: NotificationSettings[K]
  ) => {
    setNotifications({ ...notifications, [key]: value });
    setHasChanges(true);
  };

  const handleAlertChange = <K extends keyof AlertSettings>(
    key: K,
    value: AlertSettings[K]
  ) => {
    setAlerts({ ...alerts, [key]: value });
    setHasChanges(true);
  };

  const handleSave = () => {
    const orgId = getSlCurrentOrgId() || undefined;
    updateSettings(
      {
        data: {
          notifications,
          alerts,
        },
        organizationId: orgId,
      },
      {
        onSuccess: () => {
          setHasChanges(false);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">Failed to load settings. Please try again.</p>
        </div>
      </div>
    );
  }

  if (!hasPermission) {
    return (
      <div className="p-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 flex items-start gap-4">
          <Shield className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-yellow-800">Access Restricted</h3>
            <p className="text-yellow-700 mt-1">
              Only administrators can modify organization settings.
              Contact your organization administrator if you need to make changes.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">
          Configure notification preferences and alert settings for your organization.
        </p>
      </div>

      <div className="space-y-6">
        {/* Notification Settings */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Bell className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <CardTitle>Notifications</CardTitle>
                <CardDescription>
                  Configure how patients receive task reminders and alerts
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Enable Notifications */}
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="notifications-enabled" className="text-base">
                  Enable Notifications
                </Label>
                <p className="text-sm text-gray-500 mt-0.5">
                  Send automated notifications to patients
                </p>
              </div>
              <Switch
                id="notifications-enabled"
                checked={notifications.enabled}
                onCheckedChange={(checked) =>
                  handleNotificationChange('enabled', checked)
                }
              />
            </div>

            {/* Patient Reminder Channel */}
            <div className="space-y-2">
              <Label htmlFor="patient-channel">Patient Reminder Channel</Label>
              <p className="text-sm text-gray-500">
                How task reminders are sent to patients
              </p>
              <Select
                value={notifications.patient_reminder_channel}
                onValueChange={(value: 'email' | 'sms' | 'push') =>
                  handleNotificationChange('patient_reminder_channel', value)
                }
              >
                <SelectTrigger id="patient-channel" className="w-full max-w-xs text-gray-900">
                  <SelectValue placeholder="Select channel" />
                </SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="push" className="text-gray-900">Push Notification</SelectItem>
                  <SelectItem value="email" className="text-gray-900">Email</SelectItem>
                  <SelectItem value="sms" className="text-gray-900">SMS</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Care Team Alert Channel */}
            <div className="space-y-2">
              <Label htmlFor="careteam-channel">Care Team Alert Channel</Label>
              <p className="text-sm text-gray-500">
                How critical alerts are sent to the care team
              </p>
              <Select
                value={notifications.care_team_alert_channel}
                onValueChange={(value: 'email' | 'sms' | 'push' | 'all') =>
                  handleNotificationChange('care_team_alert_channel', value)
                }
              >
                <SelectTrigger id="careteam-channel" className="w-full max-w-xs text-gray-900">
                  <SelectValue placeholder="Select channel" />
                </SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="email" className="text-gray-900">Email</SelectItem>
                  <SelectItem value="push" className="text-gray-900">Push Notification</SelectItem>
                  <SelectItem value="sms" className="text-gray-900">SMS</SelectItem>
                  <SelectItem value="all" className="text-gray-900">All Channels</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Quiet Hours */}
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="quiet-hours" className="text-base">
                  Quiet Hours
                </Label>
                <p className="text-sm text-gray-500 mt-0.5">
                  Suppress non-critical notifications during specified hours
                </p>
              </div>
              <Switch
                id="quiet-hours"
                checked={notifications.quiet_hours_enabled}
                onCheckedChange={(checked) =>
                  handleNotificationChange('quiet_hours_enabled', checked)
                }
              />
            </div>
          </CardContent>
        </Card>

        {/* Alert Settings */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <CardTitle>Alert Settings</CardTitle>
                <CardDescription>
                  Configure alert escalation behavior
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Auto Escalate */}
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="auto-escalate" className="text-base">
                  Auto-Escalate Alerts
                </Label>
                <p className="text-sm text-gray-500 mt-0.5">
                  Automatically escalate unacknowledged alerts after a delay
                </p>
              </div>
              <Switch
                id="auto-escalate"
                checked={alerts.auto_escalate}
                onCheckedChange={(checked) =>
                  handleAlertChange('auto_escalate', checked)
                }
              />
            </div>

            {/* Escalation Delay */}
            <div className="space-y-2">
              <Label htmlFor="escalation-delay">Escalation Delay (minutes)</Label>
              <p className="text-sm text-gray-500">
                Time before an unacknowledged alert is escalated
              </p>
              <Select
                value={String(alerts.escalation_delay_minutes)}
                onValueChange={(value) =>
                  handleAlertChange('escalation_delay_minutes', parseInt(value, 10))
                }
                disabled={!alerts.auto_escalate}
              >
                <SelectTrigger id="escalation-delay" className="w-full max-w-xs text-gray-900">
                  <SelectValue placeholder="Select delay" />
                </SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="15" className="text-gray-900">15 minutes</SelectItem>
                  <SelectItem value="30" className="text-gray-900">30 minutes</SelectItem>
                  <SelectItem value="60" className="text-gray-900">1 hour</SelectItem>
                  <SelectItem value="120" className="text-gray-900">2 hours</SelectItem>
                  <SelectItem value="240" className="text-gray-900">4 hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end pt-4">
          <Button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
            className="min-w-[120px]"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
