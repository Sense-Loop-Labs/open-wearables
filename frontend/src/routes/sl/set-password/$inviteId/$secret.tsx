/**
 * Sense Loop Set Password Page
 * Used when accepting an invitation to join an organization
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import { Activity, AlertCircle, ArrowLeft, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useSlAuth } from '@/hooks/use-sl-auth';

export const Route = createFileRoute('/sl/set-password/$inviteId/$secret')({
  component: SlSetPasswordPage,
});

function SlSetPasswordPage() {
  const { inviteId, secret } = Route.useParams();
  const { acceptInvite, isAcceptingInvite } = useSlAuth();

  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [errors, setErrors] = useState<{ password?: string; passwordConfirm?: string; _form?: string }>({});

  const validateForm = (): boolean => {
    const newErrors: typeof errors = {};

    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 12) {
      newErrors.password = 'Password must be at least 12 characters';
    }

    if (!passwordConfirm) {
      newErrors.passwordConfirm = 'Please confirm your password';
    } else if (password !== passwordConfirm) {
      newErrors.passwordConfirm = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      await acceptInvite({
        invite_id: inviteId,
        invite_secret: secret,
        password,
        password_confirm: passwordConfirm,
      });
    } catch (error) {
      // Error is handled by the hook with toast
      setErrors({ _form: 'Failed to set password. The invitation may have expired.' });
    }
  };

  // Error state - missing params
  if (!inviteId || !secret) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black p-8">
        <div className="w-full max-w-md space-y-8 text-center">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-white">Invalid Invitation Link</h1>
          <p className="text-zinc-400">
            This invitation link is invalid. Please contact your administrator for a new invitation.
          </p>
          <Link
            to="/sl/login"
            className="inline-flex items-center gap-2 text-emerald-500 hover:text-emerald-400"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-black p-8">
      <div className="w-full max-w-md space-y-8">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <Activity className="h-10 w-10 text-emerald-500" />
          <div>
            <h1 className="text-2xl font-bold text-white">Set Your Password</h1>
            <p className="text-sm text-zinc-500">Sense Loop Clinical Dashboard</p>
          </div>
        </div>

        <p className="text-zinc-400">
          Create a secure password to complete your account setup.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Form-level error */}
          {errors._form && (
            <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20">
              <p className="text-sm text-red-500">{errors._form}</p>
            </div>
          )}

          {/* Password */}
          <div className="space-y-2">
            <Label htmlFor="password" className="text-sm font-medium text-zinc-300">
              Password
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="At least 12 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pr-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
                disabled={isAcceptingInvite}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-3 flex items-center text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.password && <p className="text-sm text-red-500">{errors.password}</p>}
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <Label htmlFor="passwordConfirm" className="text-sm font-medium text-zinc-300">
              Confirm Password
            </Label>
            <div className="relative">
              <Input
                id="passwordConfirm"
                type={showConfirmPassword ? 'text' : 'password'}
                placeholder="Confirm your password"
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                className="pr-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
                disabled={isAcceptingInvite}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute inset-y-0 right-3 flex items-center text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.passwordConfirm && <p className="text-sm text-red-500">{errors.passwordConfirm}</p>}
          </div>

          <Button
            type="submit"
            className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
            disabled={isAcceptingInvite}
          >
            {isAcceptingInvite ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating account...
              </>
            ) : (
              'Create Account'
            )}
          </Button>

          <Link
            to="/sl/login"
            className="flex items-center justify-center gap-2 text-sm text-zinc-400 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>
        </form>
      </div>
    </div>
  );
}
