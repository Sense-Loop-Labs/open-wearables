/**
 * Sense Loop Sidebar
 * Navigation sidebar for the clinical dashboard
 */

import { Link, useRouterState } from '@tanstack/react-router';
import {
  LayoutDashboard,
  Users,
  AlertTriangle,
  ClipboardList,
  Stethoscope,
  Building2,
  PanelLeft,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getSlCurrentOrgId,
  getSlOrganizations,
  setSlCurrentOrg,
} from '@/lib/auth/sl-session';

interface SlSidebarProps {
  collapsed?: boolean;
  alertCount?: number;
  onToggleCollapse?: () => void;
}

const navItems = [
  {
    label: 'Dashboard',
    path: '/sl/dashboard',
    icon: LayoutDashboard,
  },
  {
    label: 'Patients',
    path: '/sl/patients',
    icon: Users,
  },
  {
    label: 'Alerts',
    path: '/sl/alerts',
    icon: AlertTriangle,
    hasBadge: true,
  },
  {
    label: 'Care Templates',
    path: '/sl/instruction-templates',
    icon: ClipboardList,
  },
  {
    label: 'Clinicians',
    path: '/sl/clinicians',
    icon: Stethoscope,
  },
];

export function SlSidebar({ collapsed = false, alertCount = 0, onToggleCollapse }: SlSidebarProps) {
  const router = useRouterState();
  const currentPath = router.location.pathname;

  const organizations = getSlOrganizations();
  const currentOrgId = getSlCurrentOrgId();
  const currentOrg = organizations.find((o) => o.id === currentOrgId);
  const hasMultipleOrgs = organizations.length > 1;

  const handleOrgChange = (orgId: string) => {
    setSlCurrentOrg(orgId);
    window.location.reload();
  };

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 bottom-0 bg-white border-r border-gray-200 flex flex-col z-40 transition-all duration-200',
        collapsed ? 'w-16' : 'w-[250px]'
      )}
    >
      {/* Logo / Brand */}
      <div className={cn(
        'flex items-center gap-3 p-4 border-b border-gray-100',
        collapsed && 'justify-center'
      )}>
        <Activity className="w-6 h-6 text-blue-600 flex-shrink-0" />
        {!collapsed && (
          <>
            <span className="font-semibold text-gray-900 flex-1">Sense Loop</span>
            <button
              onClick={onToggleCollapse}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
              title="Collapse sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          </>
        )}
        {collapsed && (
          <button
            onClick={onToggleCollapse}
            className="absolute top-4 left-full ml-2 p-1.5 bg-white border border-gray-200 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-md shadow-sm transition-colors"
            title="Expand sidebar"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Organization Selector */}
      {!collapsed && (
        <div className="p-4 border-b border-gray-100">
          {hasMultipleOrgs ? (
            <div>
              <div className="flex items-center gap-1.5 text-xs text-gray-500 uppercase tracking-wide mb-1">
                <Building2 className="w-3 h-3" />
                <span>Organization</span>
              </div>
              <select
                value={currentOrgId || ''}
                onChange={(e) => handleOrgChange(e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md bg-white"
              >
                <option value="">Select organization</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>
          ) : currentOrg ? (
            <div>
              <div className="flex items-center gap-1.5 text-xs text-gray-500 uppercase tracking-wide mb-1">
                <Building2 className="w-3 h-3" />
                <span>Organization</span>
              </div>
              <div className="text-sm font-medium text-gray-900">{currentOrg.name}</div>
            </div>
          ) : null}
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => {
          const isActive =
            currentPath === item.path ||
            (item.path !== '/sl/dashboard' && currentPath.startsWith(item.path));

          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                collapsed && 'justify-center px-2'
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && (
                <>
                  <span>{item.label}</span>
                  {item.hasBadge && alertCount > 0 && (
                    <span className="ml-auto px-2 py-0.5 text-xs font-semibold bg-red-500 text-white rounded-full">
                      {alertCount}
                    </span>
                  )}
                </>
              )}
              {collapsed && item.hasBadge && alertCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="p-3 border-t border-gray-100">
          <p className="text-xs text-gray-400">Sense Loop v1.0</p>
        </div>
      )}
    </aside>
  );
}
