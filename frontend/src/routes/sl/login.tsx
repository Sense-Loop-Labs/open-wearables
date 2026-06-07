/**
 * Sense Loop Login Page
 * Practitioner login for the clinical dashboard
 */

import { createFileRoute, Link, redirect } from '@tanstack/react-router';
import { Activity, AlertCircle, Loader2, Mail, Lock } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSlAuth } from '@/hooks/use-sl-auth';
import { isSlAuthenticated } from '@/lib/auth/sl-session';

export const Route = createFileRoute('/sl/login')({
  beforeLoad: () => {
    // Redirect to dashboard if already authenticated
    if (isSlAuthenticated()) {
      throw redirect({ to: '/sl/dashboard' });
    }
  },
  component: SlLoginPage,
});

function SlLoginPage() {
  const { login, isLoggingIn } = useSlAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [loginError, setLoginError] = useState<string | null>(null);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};

    if (!email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Please enter a valid email';
    }

    if (!password) {
      newErrors.password = 'Password is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);

    if (!validate()) return;

    try {
      await login({ email: email.trim().toLowerCase(), password });
    } catch {
      // Always show consistent error message for security (don't reveal if email exists)
      setLoginError('Invalid email or password');
    }
  };

  const clearLoginError = () => {
    if (loginError) setLoginError(null);
  };

  return (
    <div className="flex min-h-screen bg-black">
      {/* Left side - Form */}
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <Activity className="h-10 w-10 text-emerald-500" />
            <div>
              <h1 className="text-2xl font-bold text-white">Sense Loop</h1>
              <p className="text-sm text-zinc-500">Clinical Dashboard</p>
            </div>
          </div>

          {/* Error Message */}
          {loginError && (
            <div className="flex items-center gap-3 rounded-lg border border-pink-800/50 bg-pink-950/30 p-4">
              <AlertCircle className="h-5 w-5 text-pink-400 flex-shrink-0" />
              <p className="text-sm text-pink-300">{loginError}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-zinc-300">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@hospital.org"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); clearLoginError(); }}
                    className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
                    disabled={isLoggingIn}
                  />
                </div>
                {errors.email && (
                  <p className="text-sm text-red-500">{errors.email}</p>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="text-sm font-medium text-zinc-300">
                    Password
                  </label>
                  <Link
                    to="/sl/forgot-password"
                    className="text-sm text-emerald-500 hover:text-emerald-400"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); clearLoginError(); }}
                    className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
                    disabled={isLoggingIn}
                  />
                </div>
                {errors.password && (
                  <p className="text-sm text-red-500">{errors.password}</p>
                )}
              </div>
            </div>

            <Button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              disabled={isLoggingIn}
            >
              {isLoggingIn ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-zinc-500">
            Contact your administrator if you need access to this system.
          </p>
        </div>
      </div>

      {/* Right side - Visual */}
      <div className="hidden lg:flex lg:flex-1 items-center justify-center bg-gradient-to-br from-emerald-950 via-zinc-900 to-black p-8">
        <div className="max-w-md space-y-6 text-center">
          <div className="mx-auto w-24 h-24 rounded-full bg-emerald-500/20 flex items-center justify-center">
            <Activity className="h-12 w-12 text-emerald-500" />
          </div>
          <h2 className="text-3xl font-bold text-white">
            Patient Monitoring Made Simple
          </h2>
          <p className="text-zinc-400">
            Real-time vital sign monitoring, intelligent alerts, and streamlined
            care coordination for post-operative patient recovery.
          </p>
        </div>
      </div>
    </div>
  );
}
