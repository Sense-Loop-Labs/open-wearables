import { MutationCache, QueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ApiError } from '../errors/api-error';

export const queryClient = new QueryClient({
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      // Don't show toast if mutation has its own onError handler
      // or if throwOnError is false (component handles errors)
      if (mutation.options.onError || mutation.options.throwOnError === false) {
        return;
      }

      // Don't show toast for validation errors (422) - let forms handle these
      if (error instanceof ApiError && error.statusCode === 422) {
        return;
      }

      // Show toast for other errors that aren't handled
      const message = error instanceof Error ? error.message : 'An error occurred';
      toast.error(message);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
      retry: (failureCount, error) => {
        // Don't retry on client errors (4xx)
        if (
          error instanceof ApiError &&
          error.statusCode >= 400 &&
          error.statusCode < 500
        ) {
          return false;
        }
        // Retry up to 3 times on server errors (5xx) or network errors
        return failureCount < 3;
      },
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false,
    },
  },
});
