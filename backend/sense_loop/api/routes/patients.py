"""Patient management endpoints for clinicians."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.config import sl_settings
from sense_loop.schemas.patient import (
    ConnectedDevicesResponse,
    PatientCreate,
    PatientDeviceListResponse,
    PatientDeviceResponse,
    PatientListResponse,
    PatientResponse,
    PatientSummaryResponse,
    PatientUpdate,
    SleepHistoryResponse,
    SleepReading,
    VitalReading,
    VitalsHistoryResponse,
    WearableDeviceResponse,
    WorkoutReading,
    WorkoutsHistoryResponse,
)
from sense_loop.services import EnrollmentService, PatientService

router = APIRouter()


def _get_latest_sleep_minutes(db: Session, ow_user_id: UUID | None) -> int | None:
    """Get latest sleep duration from event_record table.

    Queries the OW event_record table directly to get fresh sleep data,
    rather than relying on the potentially stale PatientSummary cache.
    """
    if not ow_user_id:
        return None

    try:
        from app.models import DataSource
        from app.models.event_record import EventRecord
        from app.models.sleep_details import SleepDetails

        # Query latest sleep record for this user
        # Use outerjoin to match mobile.py query - SleepDetails joins directly to EventRecord
        stmt = (
            select(EventRecord, SleepDetails)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .outerjoin(SleepDetails, EventRecord.id == SleepDetails.record_id)
            .where(
                DataSource.user_id == ow_user_id,
                EventRecord.category == "sleep",
            )
            .order_by(EventRecord.end_datetime.desc())
            .limit(1)
        )
        result = db.execute(stmt).first()

        if result:
            event, sleep_details = result
            if sleep_details and sleep_details.sleep_total_duration_minutes:
                return sleep_details.sleep_total_duration_minutes
            elif event.duration_seconds:
                return int(event.duration_seconds / 60)

        return None
    except Exception:
        # If OW tables aren't available, fall back to None
        return None


def _patient_to_response(patient, db: Session) -> PatientResponse:
    """Convert patient model to response schema.

    Fetches latest sleep data directly from event_record table for freshness.
    """
    summary = None
    if patient.summary:
        # Get fresh sleep data from event_record table instead of stale PatientSummary
        latest_sleep_minutes = _get_latest_sleep_minutes(db, patient.ow_user_id)

        summary = PatientSummaryResponse(
            latest_heart_rate=patient.summary.latest_heart_rate,
            latest_heart_rate_at=patient.summary.latest_heart_rate_at,
            latest_spo2=patient.summary.latest_spo2,
            latest_spo2_at=patient.summary.latest_spo2_at,
            latest_temperature=patient.summary.latest_temperature,
            latest_temperature_at=patient.summary.latest_temperature_at,
            latest_hrv=patient.summary.latest_hrv,
            latest_hrv_at=patient.summary.latest_hrv_at,
            latest_respiratory_rate=patient.summary.latest_respiratory_rate,
            latest_respiratory_rate_at=patient.summary.latest_respiratory_rate_at,
            latest_blood_pressure_systolic=patient.summary.latest_blood_pressure_systolic,
            latest_blood_pressure_diastolic=patient.summary.latest_blood_pressure_diastolic,
            latest_blood_pressure_at=patient.summary.latest_blood_pressure_at,
            today_steps=patient.summary.today_steps,
            today_active_minutes=patient.summary.today_active_minutes,
            last_sleep_duration_minutes=latest_sleep_minutes,
            active_alerts_count=patient.summary.active_alerts_count,
            active_critical_alerts_count=patient.summary.active_critical_alerts_count,
            overall_status=patient.summary.overall_status,
            last_data_received_at=patient.summary.last_data_received_at,
            # Questionnaire concerns
            has_questionnaire_concerns=patient.summary.has_questionnaire_concerns,
            questionnaire_concern_count=patient.summary.questionnaire_concern_count,
            highest_questionnaire_severity=patient.summary.highest_questionnaire_severity,
            questionnaire_concerns=patient.summary.questionnaire_concerns,
            last_questionnaire_response_at=patient.summary.last_questionnaire_response_at,
        )

    return PatientResponse(
        id=patient.id,
        organization_id=patient.organization_id,
        ow_user_id=patient.ow_user_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        age=patient.age,
        gender=patient.gender,
        email=patient.email,
        phone=patient.phone,
        mrn=patient.mrn,
        primary_diagnosis=patient.primary_diagnosis,
        surgery_date=patient.surgery_date,
        discharge_date=patient.discharge_date,
        days_post_surgery=patient.days_post_surgery,
        enrollment_status=patient.enrollment_status,
        enrolled_at=patient.enrolled_at,
        activation_code=patient.activation_code,
        activation_code_expires_at=patient.activation_code_expires_at,
        monitoring_start_date=patient.monitoring_start_date,
        monitoring_end_date=patient.monitoring_end_date,
        is_monitoring_active=patient.is_monitoring_active,
        alert_protocol_id=patient.alert_protocol_id,
        is_active=patient.is_active,
        created_at=patient.created_at,
        summary=summary,
    )


@router.get("", response_model=PatientListResponse)
async def list_patients(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(..., description="Organization ID"),
    is_active: bool | None = Query(None),
    enrollment_status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List patients in an organization."""
    # Check access using parallel mode (evaluates both legacy and Cedar)
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        organization_id,
        action="read",
        resource_type="patient",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access patients in this organization",
        )

    # Set audit context
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    # List patients
    service = PatientService(db)
    patients, total = service.list_by_organization(
        organization_id,
        is_active=is_active,
        enrollment_status=enrollment_status,
        search=search,
        page=page,
        page_size=page_size,
    )

    # Log access
    audit = AuditLogger(db)
    audit.log(
        action="list",
        resource_type="patient",
        details={
            "organization_id": str(organization_id),
            "count": len(patients),
            "filters": {
                "is_active": is_active,
                "enrollment_status": enrollment_status,
                "search": search,
            },
        },
    )
    db.commit()

    pages = (total + page_size - 1) // page_size

    # Build response items
    items = [_patient_to_response(p, db) for p in patients]

    # Filter response fields based on Cedar policies (if enabled)
    if sl_settings.use_cedar_auth:
        items = engine.filter_response_fields(
            [item.model_dump() for item in items],
            practitioner,
            "patient",
            organization_id,
        )
        # Convert back to response models
        items = [PatientResponse(**item) for item in items]

    return PatientListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get patient details."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access using parallel mode
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        patient.organization_id,
        action="read",
        resource_type="patient",
        resource_id=patient_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient",
        )

    # Log access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=["first_name", "last_name", "date_of_birth", "email", "phone"],
    )
    db.commit()

    response = _patient_to_response(patient, db)

    # Filter response fields based on Cedar policies (if enabled)
    if sl_settings.use_cedar_auth:
        filtered = engine.filter_response_fields(
            response.model_dump(),
            practitioner,
            "patient",
            patient.organization_id,
        )
        return PatientResponse(**filtered)

    return response


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    request: PatientCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new patient."""
    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_PATIENTS, request.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create patients in this organization",
        )

    # Create patient
    service = PatientService(db)
    patient = service.create(request)

    # Generate activation code
    enrollment_service = EnrollmentService(db)
    activation_code = enrollment_service.generate_activation_code(patient)

    # Log creation
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = request.organization_id

    audit = AuditLogger(db)
    audit.log_create(
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
        details={"activation_code_generated": True},
    )

    db.commit()

    # Reload to get relationships
    patient = service.get_by_id(patient.id)

    return _patient_to_response(patient, db)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    request: PatientUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update a patient."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this patient",
        )

    # Track changes for audit
    changes = {}
    update_data = request.model_dump(exclude_unset=True)
    for field, new_value in update_data.items():
        old_value = getattr(patient, field)
        if old_value != new_value:
            changes[field] = {"old": str(old_value), "new": str(new_value)}

    # Update patient
    patient = service.update(patient, request)

    # Log update
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_update(
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
        changes=changes,
    )

    db.commit()

    return _patient_to_response(patient, db)


@router.post("/{patient_id}/generate-activation-code")
async def generate_activation_code(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Generate a new activation code for a patient."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this patient",
        )

    # Generate new code
    enrollment_service = EnrollmentService(db)
    code = enrollment_service.generate_activation_code(patient)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log(
        action="generate_activation_code",
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
    )

    db.commit()

    return {
        "activation_code": code,
        "expires_at": patient.activation_code_expires_at.isoformat(),
    }


@router.post("/{patient_id}/discharge")
async def discharge_patient(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Discharge a patient from monitoring."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this patient",
        )

    # Discharge
    service.discharge(patient)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log(
        action="discharge",
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
    )

    db.commit()

    return {"success": True, "message": "Patient discharged successfully"}


# Valid vital types for filtering
VITAL_TYPES = {
    "heart_rate": {"codes": ["heart_rate"], "label": "Heart Rate", "unit": "bpm"},
    "blood_pressure": {
        "codes": ["blood_pressure_systolic", "blood_pressure_diastolic"],
        "label": "Blood Pressure",
        "unit": "mmHg",
    },
    "spo2": {"codes": ["oxygen_saturation", "spo2"], "label": "SpO2", "unit": "%"},
    "temperature": {
        "codes": ["body_temperature", "temperature"],
        "label": "Temperature",
        "unit": "°F",
    },
    "respiratory_rate": {
        "codes": ["respiratory_rate"],
        "label": "Respiratory Rate",
        "unit": "/min",
    },
    "hrv": {
        "codes": ["heart_rate_variability_sdnn", "heart_rate_variability", "hrv"],
        "label": "HRV",
        "unit": "ms",
    },
    "steps": {"codes": ["steps"], "label": "Steps", "unit": "steps"},
}


@router.get("/{patient_id}/vitals", response_model=VitalsHistoryResponse)
async def get_patient_vitals(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    vital_type: str | None = Query(None, description="Filter by vital type"),
    aggregate_hr: bool = Query(True, description="Aggregate heart rate to hourly averages"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get historical vitals for a patient.

    Returns paginated vital readings from data_point_series.
    By default, heart rate data is aggregated to hourly averages to reduce volume.
    Set aggregate_hr=false to get individual HR readings.

    Valid vital_type values: heart_rate, blood_pressure, spo2, temperature, respiratory_rate, hrv, steps
    """
    from datetime import timedelta

    from sqlalchemy import and_, func

    from app.models import DataSource
    from app.models.data_point_series import DataPointSeries
    from app.models.series_type_definition import SeriesTypeDefinition

    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        patient.organization_id,
        action="read",
        resource_type="patient",
        resource_id=patient_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's vitals",
        )

    if not patient.ow_user_id:
        return VitalsHistoryResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            pages=0,
            vital_type=vital_type,
        )

    # Validate vital_type if provided
    if vital_type and vital_type not in VITAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid vital_type. Valid values: {', '.join(VITAL_TYPES.keys())}",
        )

    # Build list of series codes to query
    if vital_type:
        codes_to_query = VITAL_TYPES[vital_type]["codes"]
    else:
        # All vitals except HR if aggregating (HR handled separately)
        # Also exclude steps from "all" view - too granular, use Workouts tab instead
        codes_to_query = []
        for vt, config in VITAL_TYPES.items():
            if vt == "steps":
                continue  # Skip steps in "all" view
            if vt != "heart_rate" or not aggregate_hr:
                codes_to_query.extend(config["codes"])

    readings: list[VitalReading] = []

    # Query non-HR vitals (or HR if not aggregating)
    if codes_to_query:
        stmt = (
            select(
                SeriesTypeDefinition.code,
                DataPointSeries.value,
                DataPointSeries.recorded_at,
                DataSource.source,
            )
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .join(
                SeriesTypeDefinition,
                DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id,
            )
            .where(
                DataSource.user_id == patient.ow_user_id,
                SeriesTypeDefinition.code.in_(codes_to_query),
            )
            .order_by(DataPointSeries.recorded_at.desc())
        )
        results = db.execute(stmt).all()

        # Process BP specially - pair systolic/diastolic by timestamp
        bp_readings: dict[str, dict] = {}  # timestamp -> {systolic, diastolic}

        for code, value, recorded_at, source in results:
            # Determine vital type from code
            vt_name = None
            for vt, config in VITAL_TYPES.items():
                if code in config["codes"]:
                    vt_name = vt
                    break

            if not vt_name:
                continue

            if vt_name == "blood_pressure":
                ts_key = recorded_at.isoformat()
                if ts_key not in bp_readings:
                    bp_readings[ts_key] = {
                        "recorded_at": recorded_at,
                        "source": source,
                        "systolic": None,
                        "diastolic": None,
                    }
                if code == "blood_pressure_systolic":
                    bp_readings[ts_key]["systolic"] = float(value)
                else:
                    bp_readings[ts_key]["diastolic"] = float(value)
            else:
                # Convert temperature from C to F if needed
                val = float(value)
                if vt_name == "temperature" and val < 50:
                    val = val * 9 / 5 + 32

                readings.append(
                    VitalReading(
                        vital_type=vt_name,
                        value=round(val, 1),
                        unit=VITAL_TYPES[vt_name]["unit"],
                        recorded_at=recorded_at,
                        source=source,
                        is_aggregated=False,
                    )
                )

        # Add paired BP readings
        for ts_key, bp in bp_readings.items():
            if bp["systolic"] is not None:
                readings.append(
                    VitalReading(
                        vital_type="blood_pressure",
                        value=bp["systolic"],
                        value_secondary=bp["diastolic"],
                        unit="mmHg",
                        recorded_at=bp["recorded_at"],
                        source=bp["source"],
                        is_aggregated=False,
                    )
                )

    # Handle aggregated HR if needed
    if (vital_type is None or vital_type == "heart_rate") and aggregate_hr:
        # Get hourly averages for HR
        from sqlalchemy import literal_column

        hr_codes = VITAL_TYPES["heart_rate"]["codes"]
        hour_col = func.date_trunc("hour", DataPointSeries.recorded_at)
        stmt = (
            select(
                hour_col.label("hour"),
                func.avg(DataPointSeries.value).label("avg_value"),
                func.count().label("count"),
            )
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .join(
                SeriesTypeDefinition,
                DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id,
            )
            .where(
                DataSource.user_id == patient.ow_user_id,
                SeriesTypeDefinition.code.in_(hr_codes),
            )
            .group_by(hour_col)
            .order_by(literal_column("hour").desc())
        )
        hr_results = db.execute(stmt).all()

        for hour, avg_value, count in hr_results:
            readings.append(
                VitalReading(
                    vital_type="heart_rate",
                    value=round(float(avg_value), 0),
                    unit="bpm",
                    recorded_at=hour,
                    source=f"avg of {count}",
                    is_aggregated=True,
                )
            )

    # Sort all readings by timestamp descending
    readings.sort(key=lambda r: r.recorded_at, reverse=True)

    # Log PHI access - vitals are clinical data
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="patient_vitals",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=[vital_type] if vital_type else list(VITAL_TYPES.keys()),
    )
    db.commit()

    # Paginate
    total = len(readings)
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = readings[start_idx:end_idx]

    return VitalsHistoryResponse(
        items=paginated,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        vital_type=vital_type,
    )


@router.get("/{patient_id}/workouts", response_model=WorkoutsHistoryResponse)
async def get_patient_workouts(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get workout history for a patient.

    Returns paginated workout records from event_record + workout_details.
    Includes walking, running, cycling, and other exercise sessions.
    """
    from app.models import DataSource
    from app.models.event_record import EventRecord
    from app.models.workout_details import WorkoutDetails

    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        patient.organization_id,
        action="read",
        resource_type="patient",
        resource_id=patient_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's workouts",
        )

    if not patient.ow_user_id:
        # No linked OW account, return empty
        return WorkoutsHistoryResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            pages=0,
        )

    # Query workouts from event_record + workout_details
    stmt = (
        select(
            EventRecord.id,
            EventRecord.type,
            EventRecord.start_datetime,
            EventRecord.end_datetime,
            EventRecord.duration_seconds,
            WorkoutDetails.distance,
            WorkoutDetails.energy_burned,
            WorkoutDetails.heart_rate_avg,
            WorkoutDetails.heart_rate_max,
            WorkoutDetails.steps_count,
            DataSource.source,
        )
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .outerjoin(WorkoutDetails, EventRecord.id == WorkoutDetails.record_id)
        .where(
            DataSource.user_id == patient.ow_user_id,
            EventRecord.category == "workout",
        )
        .order_by(EventRecord.start_datetime.desc())
    )
    results = db.execute(stmt).all()

    # Convert to WorkoutReading objects
    workouts: list[WorkoutReading] = []
    for row in results:
        (
            workout_id,
            workout_type,
            start_time,
            end_time,
            duration_seconds,
            distance,
            energy_burned,
            hr_avg,
            hr_max,
            steps,
            source,
        ) = row

        duration_min = int(duration_seconds / 60) if duration_seconds else 0

        workouts.append(
            WorkoutReading(
                id=workout_id,
                workout_type=workout_type or "Unknown",
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_min,
                distance_meters=float(distance) if distance else None,
                calories=float(energy_burned) if energy_burned else None,
                heart_rate_avg=int(hr_avg) if hr_avg else None,
                heart_rate_max=int(hr_max) if hr_max else None,
                steps=steps,
                source=source,
            )
        )

    # Log PHI access - workout/activity data
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="patient_workouts",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=["workout_type", "duration", "heart_rate", "calories"],
    )
    db.commit()

    # Paginate
    total = len(workouts)
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = workouts[start_idx:end_idx]

    return WorkoutsHistoryResponse(
        items=paginated,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{patient_id}/sleep", response_model=SleepHistoryResponse)
async def get_patient_sleep(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get sleep history for a patient.

    Returns paginated sleep records from event_record + sleep_details.
    Includes total sleep time, REM, deep, light sleep stages, and efficiency.
    """
    from app.models import DataSource
    from app.models.event_record import EventRecord
    from app.models.sleep_details import SleepDetails

    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        patient.organization_id,
        action="read",
        resource_type="patient",
        resource_id=patient_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's sleep data",
        )

    if not patient.ow_user_id:
        # No linked OW account, return empty
        return SleepHistoryResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            pages=0,
        )

    # Query sleep from event_record + sleep_details
    stmt = (
        select(
            EventRecord.id,
            EventRecord.start_datetime,
            EventRecord.end_datetime,
            SleepDetails.sleep_total_duration_minutes,
            SleepDetails.sleep_rem_minutes,
            SleepDetails.sleep_deep_minutes,
            SleepDetails.sleep_light_minutes,
            SleepDetails.sleep_awake_minutes,
            SleepDetails.sleep_efficiency_score,
            SleepDetails.is_nap,
            DataSource.source,
        )
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .outerjoin(SleepDetails, EventRecord.id == SleepDetails.record_id)
        .where(
            DataSource.user_id == patient.ow_user_id,
            EventRecord.category == "sleep",
        )
        .order_by(EventRecord.start_datetime.desc())
    )
    results = db.execute(stmt).all()

    # Convert to SleepReading objects
    sleep_records: list[SleepReading] = []
    for row in results:
        (
            record_id,
            start_time,
            end_time,
            total_min,
            rem_min,
            deep_min,
            light_min,
            awake_min,
            efficiency,
            is_nap,
            source,
        ) = row

        sleep_records.append(
            SleepReading(
                id=record_id,
                start_time=start_time,
                end_time=end_time,
                total_minutes=total_min,
                rem_minutes=rem_min,
                deep_minutes=deep_min,
                light_minutes=light_min,
                awake_minutes=awake_min,
                efficiency_percent=float(efficiency) if efficiency else None,
                is_nap=is_nap or False,
                source=source,
            )
        )

    # Log PHI access - sleep data
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="patient_sleep",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=["sleep_duration", "sleep_stages", "sleep_efficiency"],
    )
    db.commit()

    # Paginate
    total = len(sleep_records)
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = sleep_records[start_idx:end_idx]

    return SleepHistoryResponse(
        items=paginated,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{patient_id}/devices", response_model=ConnectedDevicesResponse)
async def get_patient_devices(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get connected devices for a patient.

    Returns both:
    - Wearable devices that send health data (Apple Watch, Fitbit, scales, etc.)
    - App installations registered for push notifications
    """
    from sqlalchemy import func

    from app.models import DataSource
    from app.models.data_point_series import DataPointSeries
    from sense_loop.models import PatientDevice

    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        patient.organization_id,
        action="read",
        resource_type="patient",
        resource_id=patient_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's devices",
        )

    # Get wearable devices from DataSource (health data sources)
    wearables: list[WearableDeviceResponse] = []
    if patient.ow_user_id:
        # Get data sources with their latest data timestamp
        stmt = (
            select(
                DataSource,
                func.max(DataPointSeries.recorded_at).label("last_data_at"),
            )
            .outerjoin(DataPointSeries, DataSource.id == DataPointSeries.data_source_id)
            .where(DataSource.user_id == patient.ow_user_id)
            .group_by(DataSource.id)
            .order_by(func.max(DataPointSeries.recorded_at).desc().nulls_last())
        )
        results = db.execute(stmt).all()

        for ds, last_data_at in results:
            # Use source (device name) or fall back to device_model or provider
            name = ds.source or ds.original_source_name or ds.device_model or ds.provider
            wearables.append(
                WearableDeviceResponse(
                    id=ds.id,
                    name=name,
                    device_model=ds.device_model,
                    device_type=ds.device_type,
                    provider=ds.provider,
                    last_data_at=last_data_at,
                )
            )

    # Get app installations (for push notifications)
    stmt = (
        select(PatientDevice)
        .where(PatientDevice.patient_id == patient_id)
        .order_by(PatientDevice.last_used_at.desc().nulls_last())
    )
    devices = db.execute(stmt).scalars().all()

    app_installations = [
        PatientDeviceResponse(
            id=d.id,
            platform=d.platform,
            device_name=d.device_name,
            app_version=d.app_version,
            is_active=d.is_active,
            last_used_at=d.last_used_at,
            created_at=d.created_at,
        )
        for d in devices
    ]

    # Log device access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="patient_devices",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=["device_info", "data_sources"],
    )
    db.commit()

    return ConnectedDevicesResponse(
        wearables=wearables,
        app_installations=app_installations,
    )
