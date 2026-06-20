import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router';
import { isAuthenticated } from '@/lib/auth/session';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useEffect } from 'react';
import { DEFAULT_REDIRECTS, SL_ROUTES } from '@/lib/constants/routes';

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    // During SSR, always redirect to SL login (can't check auth without localStorage)
    if (typeof window === 'undefined') {
      throw redirect({ to: SL_ROUTES.login });
    }
    // Client-side: redirect based on auth status
    if (isAuthenticated()) {
      throw redirect({
        to: DEFAULT_REDIRECTS.authenticated,
      });
    } else {
      throw redirect({
        to: DEFAULT_REDIRECTS.unauthenticated,
      });
    }
  },
  component: IndexRedirect,
});

function IndexRedirect() {
  const navigate = useNavigate();

  // Handle client-side redirect after hydration (fallback)
  useEffect(() => {
    if (isAuthenticated()) {
      navigate({ to: DEFAULT_REDIRECTS.authenticated });
    } else {
      navigate({ to: DEFAULT_REDIRECTS.unauthenticated });
    }
  }, [navigate]);

  // Always render the same content on both server and client to avoid hydration mismatch
  return (
    <div className="min-h-screen flex items-center justify-center bg-black">
      <LoadingSpinner size="lg" />
    </div>
  );
}
