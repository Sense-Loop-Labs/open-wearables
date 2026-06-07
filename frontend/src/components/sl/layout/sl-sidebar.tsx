/**
 * Sense Loop Sidebar
 * Navigation sidebar for the clinical dashboard
 */

import { Link, useRouterState } from '@tanstack/react-router';
import {
  Activity,
  AlertTriangle,
  LayoutDashboard,
  LogOut,
  Settings,
  Users,
  UserCog,
  Building2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSlAuth } from '@/hooks/use-sl-auth';
import {
  getSlCurrentOrgId,
  getSlOrganizations,
  setSlCurrentOrg,
} from '@/lib/auth/sl-session';

interface NavItem {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/sl/dashboard', icon: LayoutDashboard },
  { label: 'Patients', to: '/sl/patients', icon: Users },
  { label: 'Alerts', to: '/sl/alerts', icon: AlertTriangle },
  { label: 'Clinicians', to: '/sl/clinicians', icon: UserCog },
  { label: 'Settings', to: '/sl/settings', icon: Settings },
];

export function SlSidebar() {
  const { logout, practitioner } = useSlAuth();
  const router = useRouterState();
  const currentPath = router.location.pathname;

  const organizations = getSlOrganizations();
  const currentOrgId = getSlCurrentOrgId();

  const handleOrgChange = (orgId: string) => {
    setSlCurrentOrg(orgId);
    // Force a page refresh to reload data for new org
    window.location.reload();
  };

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-zinc-800 bg-black">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-zinc-800 px-6">
        <Activity className="h-6 w-6 text-emerald-500" />
        <span className="text-lg font-semibold text-white">Sense Loop</span>
      </div>

      {/* Organization Selector */}
      {organizations.length > 1 && (
        <div className="border-b border-zinc-800 px-4 py-3">
          <Select value={currentOrgId || ''} onValueChange={handleOrgChange}>
            <SelectTrigger className="w-full bg-zinc-900 border-zinc-700">
              <Building2 className="mr-2 h-4 w-4 text-zinc-400" />
              <SelectValue placeholder="Select organization" />
            </SelectTrigger>
            <SelectContent>
              {organizations.map((org) => (
                <SelectItem key={org.id} value={org.id}>
                  <div className="flex flex-col">
                    <span>{org.name}</span>
                    <span className="text-xs text-zinc-500">{org.role_display_name}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive = currentPath === item.to || currentPath.startsWith(`${item.to}/`);
          const Icon = item.icon;

          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-zinc-800 text-white border-l-2 border-emerald-500'
                  : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
              }`}
            >
              <Icon className={`h-5 w-5 ${isActive ? 'text-emerald-500' : ''}`} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User & Logout */}
      <div className="border-t border-zinc-800 p-4">
        {practitioner && (
          <div className="mb-3 px-2">
            <p className="text-sm font-medium text-white truncate">
              {practitioner.fullName}
            </p>
            <p className="text-xs text-zinc-500 truncate">{practitioner.email}</p>
            {practitioner.currentOrg && (
              <p className="text-xs text-emerald-500 mt-1">
                {practitioner.currentOrg.role_display_name}
              </p>
            )}
          </div>
        )}
        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-zinc-700 text-zinc-400 hover:text-white"
          onClick={() => logout()}
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
