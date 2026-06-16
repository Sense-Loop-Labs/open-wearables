"""Patient service - patient CRUD operations."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import Patient, PatientSummary
from sense_loop.schemas.patient import PatientCreate, PatientUpdate

logger = logging.getLogger(__name__)


class PatientService:
    """Service for patient management."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, patient_id: UUID) -> Patient | None:
        """Get patient by ID with relationships loaded."""
        stmt = (
            select(Patient)
            .where(Patient.id == patient_id)
            .options(
                joinedload(Patient.organization),
                joinedload(Patient.summary),
                joinedload(Patient.alert_protocol),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_ow_user_id(self, ow_user_id: UUID) -> Patient | None:
        """Get patient by OW User ID."""
        stmt = (
            select(Patient)
            .where(Patient.ow_user_id == ow_user_id)
            .options(
                joinedload(Patient.organization),
                joinedload(Patient.summary),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_activation_code(self, code: str) -> Patient | None:
        """Get patient by activation code."""
        stmt = (
            select(Patient)
            .where(Patient.activation_code == code)
            .options(joinedload(Patient.organization))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def list_by_organization(
        self,
        organization_id: UUID,
        *,
        is_active: bool | None = None,
        enrollment_status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Patient], int]:
        """List patients in an organization with filtering."""
        stmt = (
            select(Patient)
            .where(Patient.organization_id == organization_id)
            .options(joinedload(Patient.summary))
        )

        if is_active is not None:
            stmt = stmt.where(Patient.is_active == is_active)

        if enrollment_status:
            stmt = stmt.where(Patient.enrollment_status == enrollment_status)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                (Patient.first_name.ilike(search_pattern))
                | (Patient.last_name.ilike(search_pattern))
                | (Patient.mrn.ilike(search_pattern))
                | (Patient.email.ilike(search_pattern))
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginate
        stmt = stmt.order_by(Patient.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        patients = self.db.execute(stmt).unique().scalars().all()
        return list(patients), total

    def create(self, data: PatientCreate) -> Patient:
        """Create a new patient."""
        patient = Patient(
            id=uuid4(),
            organization_id=data.organization_id,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            email=data.email,
            phone=data.phone,
            address=data.address,
            mrn=data.mrn,
            primary_diagnosis=data.primary_diagnosis,
            surgery_date=data.surgery_date,
            discharge_date=data.discharge_date,
            alert_protocol_id=data.alert_protocol_id,
            monitoring_start_date=data.monitoring_start_date,
            monitoring_end_date=data.monitoring_end_date,
            enrollment_status="pending",
        )

        self.db.add(patient)

        # Create empty summary
        summary = PatientSummary(
            id=uuid4(),
            patient_id=patient.id,
        )
        self.db.add(summary)

        self.db.flush()

        logger.info("Created patient %s in org %s", patient.id, data.organization_id)
        return patient

    def update(self, patient: Patient, data: PatientUpdate) -> Patient:
        """Update a patient."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(patient, field, value)

        self.db.flush()

        logger.info("Updated patient %s", patient.id)
        return patient

    def link_ow_user(self, patient: Patient, ow_user_id: UUID) -> Patient:
        """Link patient to an OW User."""
        patient.ow_user_id = ow_user_id
        self.db.flush()

        logger.info("Linked patient %s to OW user %s", patient.id, ow_user_id)
        return patient

    def deactivate(self, patient: Patient) -> Patient:
        """Deactivate a patient."""
        patient.is_active = False
        self.db.flush()

        logger.info("Deactivated patient %s", patient.id)
        return patient

    def discharge(self, patient: Patient) -> Patient:
        """Discharge a patient from monitoring."""
        from datetime import datetime

        patient.enrollment_status = "discharged"
        patient.discharged_at = datetime.utcnow()
        self.db.flush()

        logger.info("Discharged patient %s", patient.id)
        return patient
