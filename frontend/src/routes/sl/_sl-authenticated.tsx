/**
 * Sense Loop Authenticated Layout
 * Wraps all authenticated /sl/* routes with auth guard and sidebar
 */

import { useEffect } from 'react';
import { createFileRoute, Outlet, redirect, useNavigate } from '@tanstack/react-router';

import { SlSidebar } from '@/components/sl/layout/sl-sidebar';
import { isSlAuthenticated } from '@/lib/auth/sl-session';

export const Route = createFileRoute('/sl/_sl-authenticated')({
  beforeLoad: () => {
    // Skip auth check during SSR - client will handle authentication
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
    <div className="flex h-screen bg-black">
      <SlSidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
