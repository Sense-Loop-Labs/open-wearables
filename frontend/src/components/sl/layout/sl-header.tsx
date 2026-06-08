/**
 * Sense Loop Header
 * Minimal header with user info
 */

import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { LogOut, Settings, User, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getSlCurrentPractitioner,
  clearSlSession,
} from '@/lib/auth/sl-session';

export function SlHeader() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const practitioner = getSlCurrentPractitioner();

  const handleLogout = () => {
    clearSlSession();
    navigate({ to: '/sl/login' });
  };

  const getInitials = () => {
    if (!practitioner) return '?';
    const first = practitioner.firstName?.[0] || '';
    const last = practitioner.lastName?.[0] || '';
    return (first + last).toUpperCase() || '?';
  };

  return (
    <header className="flex items-center justify-end px-6 py-4">
      {/* User Info */}
      <div className="sl-avatar-dropdown relative">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex items-center gap-3 hover:bg-gray-50 rounded-lg px-3 py-2 transition-colors"
        >
          <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
            <User className="w-5 h-5 text-gray-500" />
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold text-[var(--sl-text-primary)]">
              {practitioner?.fullName || 'User'}
              {practitioner?.currentOrg?.role_display_name && (
                <span className="font-normal text-gray-500">
                  , {practitioner.currentOrg.role_display_name}
                </span>
              )}
            </p>
            <p className="text-xs text-green-600 font-medium">On Call</p>
          </div>
          <ChevronDown className={cn(
            'w-4 h-4 text-gray-400 transition-transform',
            menuOpen && 'rotate-180'
          )} />
        </button>

        {menuOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setMenuOpen(false)}
            />
            <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg min-w-[200px] z-50">
              {practitioner && (
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">
                    {practitioner.fullName}
                  </p>
                  <p className="text-xs text-gray-500">{practitioner.email}</p>
                </div>
              )}
              <div className="py-1">
                <button className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                  <User className="w-4 h-4" />
                  Profile
                </button>
                <button className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                  <Settings className="w-4 h-4" />
                  Settings
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  <LogOut className="w-4 h-4" />
                  Sign out
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
