/**
 * Sense Loop Session Management
 * Separate session storage for practitioner authentication
 */

import type { PractitionerOrgInfo } from '../api/types/sense-loop';

const SL_AUTH_TOKEN_KEY = 'sl_auth_token';
const SL_REFRESH_TOKEN_KEY = 'sl_refresh_token';
const SL_PRACTITIONER_ID_KEY = 'sl_practitioner_id';
const SL_PRACTITIONER_EMAIL_KEY = 'sl_practitioner_email';
const SL_PRACTITIONER_NAME_KEY = 'sl_practitioner_name';
const SL_SESSION_EXPIRY_KEY = 'sl_session_expiry';
const SL_ORGANIZATIONS_KEY = 'sl_organizations';
const SL_CURRENT_ORG_KEY = 'sl_current_org';

// Default session duration: 24 hours
const DEFAULT_SESSION_DURATION_MS = 24 * 60 * 60 * 1000;

export interface SlSessionData {
  accessToken: string;
  refreshToken: string;
  practitionerId: string;
  email: string;
  firstName: string;
  lastName: string;
  organizations: PractitionerOrgInfo[];
  expiresIn: number;
}

export interface SlCurrentPractitioner {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  fullName: string;
  organizations: PractitionerOrgInfo[];
  currentOrgId: string | null;
  currentOrg: PractitionerOrgInfo | null;
}

/**
 * Check if we're in a browser environment
 */
function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof localStorage !== 'undefined';
}

/**
 * Set the practitioner session data
 */
export function setSlSession(data: SlSessionData): void {
  if (!isBrowser()) return;

  const expiryTime = Date.now() + (data.expiresIn * 1000 || DEFAULT_SESSION_DURATION_MS);

  localStorage.setItem(SL_AUTH_TOKEN_KEY, data.accessToken);
  localStorage.setItem(SL_REFRESH_TOKEN_KEY, data.refreshToken);
  localStorage.setItem(SL_PRACTITIONER_ID_KEY, data.practitionerId);
  localStorage.setItem(SL_PRACTITIONER_EMAIL_KEY, data.email);
  localStorage.setItem(SL_PRACTITIONER_NAME_KEY, `${data.firstName} ${data.lastName}`);
  localStorage.setItem(SL_SESSION_EXPIRY_KEY, expiryTime.toString());
  localStorage.setItem(SL_ORGANIZATIONS_KEY, JSON.stringify(data.organizations));

  // Set current org to first org if not already set
  if (data.organizations.length > 0 && !localStorage.getItem(SL_CURRENT_ORG_KEY)) {
    localStorage.setItem(SL_CURRENT_ORG_KEY, data.organizations[0].id);
  }
}

/**
 * Clear the practitioner session
 */
export function clearSlSession(): void {
  if (!isBrowser()) return;

  localStorage.removeItem(SL_AUTH_TOKEN_KEY);
  localStorage.removeItem(SL_REFRESH_TOKEN_KEY);
  localStorage.removeItem(SL_PRACTITIONER_ID_KEY);
  localStorage.removeItem(SL_PRACTITIONER_EMAIL_KEY);
  localStorage.removeItem(SL_PRACTITIONER_NAME_KEY);
  localStorage.removeItem(SL_SESSION_EXPIRY_KEY);
  localStorage.removeItem(SL_ORGANIZATIONS_KEY);
  localStorage.removeItem(SL_CURRENT_ORG_KEY);
}

/**
 * Get the current auth token
 */
export function getSlToken(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem(SL_AUTH_TOKEN_KEY);
}

/**
 * Get the refresh token
 */
export function getSlRefreshToken(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem(SL_REFRESH_TOKEN_KEY);
}

/**
 * Check if the practitioner is authenticated
 */
export function isSlAuthenticated(): boolean {
  if (!isBrowser()) return false;

  const token = getSlToken();
  const expiry = localStorage.getItem(SL_SESSION_EXPIRY_KEY);

  if (!token || !expiry) {
    return false;
  }

  const expiryTime = parseInt(expiry, 10);
  if (isNaN(expiryTime) || Date.now() > expiryTime) {
    clearSlSession();
    return false;
  }

  return true;
}

/**
 * Check if session is expiring soon (within 5 minutes)
 */
export function isSlSessionExpiringSoon(): boolean {
  if (!isBrowser()) return true;

  const expiry = localStorage.getItem(SL_SESSION_EXPIRY_KEY);
  if (!expiry) return true;

  const expiryTime = parseInt(expiry, 10);
  const fiveMinutes = 5 * 60 * 1000;

  return Date.now() > (expiryTime - fiveMinutes);
}

/**
 * Get the current practitioner info
 */
export function getSlCurrentPractitioner(): SlCurrentPractitioner | null {
  if (!isBrowser() || !isSlAuthenticated()) {
    return null;
  }

  const id = localStorage.getItem(SL_PRACTITIONER_ID_KEY);
  const email = localStorage.getItem(SL_PRACTITIONER_EMAIL_KEY);
  const fullName = localStorage.getItem(SL_PRACTITIONER_NAME_KEY);
  const orgsJson = localStorage.getItem(SL_ORGANIZATIONS_KEY);
  const currentOrgId = localStorage.getItem(SL_CURRENT_ORG_KEY);

  if (!id || !email) {
    return null;
  }

  const organizations: PractitionerOrgInfo[] = orgsJson ? JSON.parse(orgsJson) : [];
  const [firstName, ...lastNameParts] = (fullName || '').split(' ');
  const lastName = lastNameParts.join(' ');
  const currentOrg = currentOrgId
    ? organizations.find(o => o.id === currentOrgId) || null
    : null;

  return {
    id,
    email,
    firstName: firstName || '',
    lastName: lastName || '',
    fullName: fullName || '',
    organizations,
    currentOrgId,
    currentOrg,
  };
}

/**
 * Set the current organization
 */
export function setSlCurrentOrg(orgId: string): void {
  if (!isBrowser()) return;
  localStorage.setItem(SL_CURRENT_ORG_KEY, orgId);
}

/**
 * Get the current organization ID
 */
export function getSlCurrentOrgId(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem(SL_CURRENT_ORG_KEY);
}

/**
 * Get all organizations the practitioner has access to
 */
export function getSlOrganizations(): PractitionerOrgInfo[] {
  if (!isBrowser()) return [];
  const orgsJson = localStorage.getItem(SL_ORGANIZATIONS_KEY);
  return orgsJson ? JSON.parse(orgsJson) : [];
}
