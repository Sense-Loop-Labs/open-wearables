"""FHIR export service - on-demand FHIR export for EHR integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from sense_loop.models import Alert, CarePlan, Patient

logger = logging.getLogger(__name__)


class FHIRExportService:
    """Service for exporting patient data as FHIR resources."""

    def __init__(self, db: Session):
        self.db = db

    def export_patient(self, patient_id: UUID) -> dict[str, Any]:
        """Export patient data as FHIR Bundle.

        Returns a FHIR Bundle containing:
        - Patient resource
        - Flag resources (from alerts)
        - CarePlan resources
        """
        patient = self._get_patient(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "entry": [],
        }

        # Add Patient resource
        patient_resource = self._patient_to_fhir(patient)
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{patient.id}",
            "resource": patient_resource,
        })

        # Add Flag resources (from alerts)
        alerts = self._get_patient_alerts(patient_id)
        for alert in alerts:
            flag_resource = self._alert_to_fhir_flag(alert, patient)
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{alert.id}",
                "resource": flag_resource,
            })

        # Add CarePlan resources
        care_plans = self._get_patient_care_plans(patient_id)
        for plan in care_plans:
            plan_resource = self._care_plan_to_fhir(plan, patient)
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{plan.id}",
                "resource": plan_resource,
            })

        logger.info(
            "Exported FHIR bundle for patient %s with %d entries",
            patient_id,
            len(bundle["entry"]),
        )

        return bundle

    def _get_patient(self, patient_id: UUID) -> Patient | None:
        """Get patient by ID."""
        stmt = select(Patient).where(Patient.id == patient_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def _get_patient_alerts(self, patient_id: UUID) -> list[Alert]:
        """Get all alerts for a patient."""
        stmt = (
            select(Alert)
            .where(Alert.patient_id == patient_id)
            .order_by(Alert.triggered_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _get_patient_care_plans(self, patient_id: UUID) -> list[CarePlan]:
        """Get all care plans for a patient."""
        stmt = (
            select(CarePlan)
            .where(CarePlan.patient_id == patient_id)
            .order_by(CarePlan.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _patient_to_fhir(self, patient: Patient) -> dict[str, Any]:
        """Convert patient to FHIR Patient resource."""
        resource = {
            "resourceType": "Patient",
            "id": str(patient.id),
            "meta": {
                "lastUpdated": patient.created_at.isoformat() + "Z",
            },
            "active": patient.is_active,
            "name": [
                {
                    "use": "official",
                    "family": patient.last_name,
                    "given": [patient.first_name],
                }
            ],
            "birthDate": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        }

        # Add identifier (MRN)
        if patient.mrn:
            resource["identifier"] = [
                {
                    "use": "usual",
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                "code": "MR",
                                "display": "Medical Record Number",
                            }
                        ]
                    },
                    "value": patient.mrn,
                }
            ]

        # Add gender
        if patient.gender:
            gender_map = {
                "male": "male",
                "female": "female",
                "other": "other",
                "unknown": "unknown",
            }
            resource["gender"] = gender_map.get(patient.gender.lower(), "unknown")

        # Add telecom
        telecom = []
        if patient.email:
            telecom.append({
                "system": "email",
                "value": patient.email,
            })
        if patient.phone:
            telecom.append({
                "system": "phone",
                "value": patient.phone,
            })
        if telecom:
            resource["telecom"] = telecom

        return resource

    def _alert_to_fhir_flag(self, alert: Alert, patient: Patient) -> dict[str, Any]:
        """Convert alert to FHIR Flag resource."""
        # Map severity to FHIR flag status
        status = "active" if alert.status == "active" else "inactive"

        # Build category coding
        category_code = "admin"  # Default
        if alert.category == "vital_sign":
            category_code = "clinical"
        elif alert.category == "questionnaire":
            category_code = "behavioral"

        resource = {
            "resourceType": "Flag",
            "id": str(alert.id),
            "meta": {
                "lastUpdated": (alert.resolved_at or alert.triggered_at).isoformat() + "Z",
            },
            "status": status,
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/flag-category",
                            "code": category_code,
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://senselooplabs.com/fhir/alert-code",
                        "code": alert.vital_type or alert.category,
                        "display": alert.title,
                    }
                ],
                "text": alert.title,
            },
            "subject": {
                "reference": f"Patient/{patient.id}",
                "display": patient.full_name,
            },
            "period": {
                "start": alert.triggered_at.isoformat() + "Z",
            },
        }

        if alert.resolved_at:
            resource["period"]["end"] = alert.resolved_at.isoformat() + "Z"

        return resource

    def _care_plan_to_fhir(self, plan: CarePlan, patient: Patient) -> dict[str, Any]:
        """Convert care plan to FHIR CarePlan resource."""
        # Map status
        status_map = {
            "draft": "draft",
            "active": "active",
            "completed": "completed",
            "cancelled": "revoked",
        }
        status = status_map.get(plan.status, "unknown")

        resource = {
            "resourceType": "CarePlan",
            "id": str(plan.id),
            "meta": {
                "lastUpdated": plan.updated_at.isoformat() + "Z",
            },
            "status": status,
            "intent": "plan",
            "title": plan.title,
            "description": plan.description,
            "subject": {
                "reference": f"Patient/{patient.id}",
                "display": patient.full_name,
            },
            "period": {
                "start": plan.start_date.isoformat(),
            },
            "created": plan.created_at.isoformat() + "Z",
        }

        if plan.end_date:
            resource["period"]["end"] = plan.end_date.isoformat()

        # Add category
        category_map = {
            "discharge": "discharge",
            "follow_up": "assess-plan",
            "medication": "medication",
            "activity": "activity",
            "dietary": "diet",
        }
        category_code = category_map.get(plan.plan_type, "assess-plan")
        resource["category"] = [
            {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/care-plan-category",
                        "code": category_code,
                    }
                ]
            }
        ]

        return resource
