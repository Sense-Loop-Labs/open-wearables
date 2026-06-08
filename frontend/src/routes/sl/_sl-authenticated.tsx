/**
 * Sense Loop Authenticated Layout
 * Wraps all authenticated /sl/* routes with auth guard and sidebar
 */

import { useEffect, useState } from 'react';
import { createFileRoute, Outlet, redirect, useNavigate } from '@tanstack/react-router';

import { SlSidebar } from '@/components/sl/layout/sl-sidebar';
import { SlHeader } from '@/components/sl/layout/sl-header';
import { isSlAuthenticated } from '@/lib/auth/sl-session';
import { useSlAlerts } from '@/hooks/api/use-sl-alerts';
import '@/styles/sl-clinical.css';

export const Route = createFileRoute('/sl/_sl-authenticated')({
  beforeLoad: () => {
    if (typeof window === 'undefined') {
      return;
    }

    if (!isSlAuthenticated()) {
      throw redirect({
        to: '/sl/login',
      });
    }
  },
  component: SlAuthenticatedLayout,
});

function SlAuthenticatedLayout() {
  const navigate = useNavigate();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Get active alert count for sidebar badge
  const { data: alertsData } = useSlAlerts({ status: 'active', page_size: 1 });
  const alertCount = alertsData?.total ?? 0;

  // Client-side auth check after hydration
  useEffect(() => {
    if (!isSlAuthenticated()) {
      navigate({ to: '/sl/login' });
    }
  }, [navigate]);

  // Don't render content if not authenticated (prevents flash)
  if (typeof window !== 'undefined' && !isSlAuthenticated()) {
    return null;
  }

  return (
    <div className="sl-clinical flex min-h-screen bg-gray-50">
      <SlSidebar
        collapsed={sidebarCollapsed}
        alertCount={alertCount}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div
        className="flex-1 flex flex-col transition-all duration-200"
        style={{ marginLeft: sidebarCollapsed ? '64px' : '250px' }}
      >
        <SlHeader />
        <main className="flex-1 px-8 pb-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
