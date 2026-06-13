/**
 * Sense Loop Authentication Hook
 * Handles practitioner login, logout, and session management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';

import { slAuthService } from '@/lib/api/services/sense-loop.service';
import type {
  AcceptInviteRequest,
  ForgotPasswordRequest,
  PractitionerLoginRequest,
  ResetPasswordRequest,
} from '@/lib/api/types/sense-loop';
import {
  clearSlSession,
  getSlCurrentPractitioner,
  isSlAuthenticated,
  setSlSession,
} from '@/lib/auth/sl-session';
import { queryKeys } from '@/lib/query/keys';

export function useSlAuth() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Current practitioner query
  const { data: practitioner, isLoading: isLoadingPractitioner } = useQuery({
    queryKey: queryKeys.sl.auth.me(),
    queryFn: () => getSlCurrentPractitioner(),
    enabled: isSlAuthenticated(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: (credentials: PractitionerLoginRequest) =>
      slAuthService.login(credentials),
    onSuccess: (response) => {
      setSlSession({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        practitionerId: response.practitioner_id,
        email: response.email,
        firstName: response.first_name,
        lastName: response.last_name,
        organizations: response.organizations,
        expiresIn: response.expires_in,
      });

      // Invalidate session query to refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.sl.auth.all });

      toast.success('Welcome back!');
      navigate({ to: '/sl/dashboard' });
    },
    onError: () => {
      // Error is handled by the login form with inline message
    },
  });

  // Logout mutation
  const logoutMutation = useMutation({
    mutationFn: () => slAuthService.logout(),
    onSuccess: () => {
      clearSlSession();
      queryClient.clear();
      navigate({ to: '/sl/login' });
    },
    onError: () => {
      // Clear session even if API call fails
      clearSlSession();
      queryClient.clear();
      navigate({ to: '/sl/login' });
    },
  });

  // Forgot password mutation
  const forgotPasswordMutation = useMutation({
    mutationFn: (data: ForgotPasswordRequest) => slAuthService.forgotPassword(data),
    onSuccess: () => {
      toast.success('If an account exists with this email, you will receive a password reset link.');
    },
    onError: () => {
      // Don't reveal if email exists or not
      toast.success('If an account exists with this email, you will receive a password reset link.');
    },
  });

  // Reset password mutation
  const resetPasswordMutation = useMutation({
    mutationFn: (data: ResetPasswordRequest) => slAuthService.resetPassword(data),
    onSuccess: () => {
      toast.success('Password reset successfully. You can now log in.');
      navigate({ to: '/sl/login' });
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reset password');
    },
  });

  // Accept invite mutation
  const acceptInviteMutation = useMutation({
    mutationFn: (data: AcceptInviteRequest) => slAuthService.acceptInvite(data),
    onSuccess: () => {
      toast.success('Account created successfully. You can now log in.');
      navigate({ to: '/sl/login' });
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to accept invitation');
    },
  });

  return {
    // State
    practitioner,
    isAuthenticated: isSlAuthenticated(),
    isLoading: isLoadingPractitioner,

    // Mutations
    login: loginMutation.mutateAsync,
    logout: logoutMutation.mutate,
    forgotPassword: forgotPasswordMutation.mutateAsync,
    resetPassword: resetPasswordMutation.mutateAsync,
    acceptInvite: acceptInviteMutation.mutateAsync,

    // Loading states
    isLoggingIn: loginMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
    isSendingResetEmail: forgotPasswordMutation.isPending,
    isResettingPassword: resetPasswordMutation.isPending,
    isAcceptingInvite: acceptInviteMutation.isPending,
  };
}
