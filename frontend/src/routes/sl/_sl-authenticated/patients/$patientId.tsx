/**
 * Patient Layout Route
 * This is a layout route that renders child routes via Outlet
 */

import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute(
  '/sl/_sl-authenticated/patients/$patientId'
)({
  component: PatientLayout,
});

function PatientLayout() {
  return <Outlet />;
}
