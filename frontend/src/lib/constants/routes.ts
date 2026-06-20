export const ROUTES = {
  // Public routes (Open Wearables - legacy)
  login: '/login',
  register: '/register',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',

  // Authenticated routes (Open Wearables - legacy)
  dashboard: '/dashboard',
  users: '/users',
  webhooks: '/webhooks',
  settings: '/settings',

  // Widget routes
  widgetConnect: '/widget/connect',
} as const;

// Sense Loop routes (clinician dashboard)
export const SL_ROUTES = {
  login: '/sl/login',
  forgotPassword: '/sl/forgot-password',
  dashboard: '/sl/dashboard',
  patients: '/sl/patients',
  alerts: '/sl/alerts',
  clinicians: '/sl/clinicians',
  instructionTemplates: '/sl/instruction-templates',
} as const;

// Default redirects point to Sense Loop (clinician dashboard)
export const DEFAULT_REDIRECTS = {
  authenticated: SL_ROUTES.dashboard,
  unauthenticated: SL_ROUTES.login,
} as const;
