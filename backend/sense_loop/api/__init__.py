"""Sense Loop API routes."""

from fastapi import APIRouter

from .routes import auth, mobile, patients, alerts, clinicians, organizations, dashboard, value_sets, clinical_actions, break_glass, instruction_templates

sl_router = APIRouter(prefix="/sl", tags=["Sense Loop"])

# Patient auth endpoints (public)
sl_router.include_router(auth.router, prefix="/auth", tags=["SL: Auth"])

# Mobile data endpoints (SDK token required)
sl_router.include_router(mobile.router, prefix="/data", tags=["SL: Mobile Data"])

# Clinician dashboard endpoints (Practitioner token required)
sl_router.include_router(patients.router, prefix="/patients", tags=["SL: Patients"])
sl_router.include_router(alerts.router, prefix="/alerts", tags=["SL: Alerts"])
sl_router.include_router(clinicians.router, prefix="/clinicians", tags=["SL: Clinicians"])
sl_router.include_router(organizations.router, prefix="/organizations", tags=["SL: Organizations"])
sl_router.include_router(dashboard.router, prefix="/dashboard", tags=["SL: Dashboard"])
sl_router.include_router(value_sets.router, prefix="/value-sets", tags=["SL: Value Sets"])
sl_router.include_router(clinical_actions.router, prefix="/patients", tags=["SL: Clinical Actions"])
sl_router.include_router(break_glass.router, prefix="/break-glass", tags=["SL: Break-the-Glass"])
sl_router.include_router(instruction_templates.router, prefix="/instruction-templates", tags=["SL: Instruction Templates"])

__all__ = ["sl_router"]
