"""Mobile data endpoints for iOS app."""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.database import DbSession
from sense_loop.schemas.mobile import (
    ActivitySummary,
    BloodPressureSummary,
    CarePlanResponse,
    DashboardSummaryResponse,
    HeartRateSummary,
    HRVSummary,
    HRVTrendPoint,
    QuestionnaireSubmitRequest,
    QuestionnaireSubmitResponse,
    RecoverySummary,
    RestingHeartRateSummary,
    RestingHRTrendPoint,
    SleepSummary,
    SleepTrendPoint,
    TemperatureSummary,
    TodayActivity,
    VitalsSummary,
    WeeklyActivityPoint,
    WeightSummary,
)
from sense_loop.services import CarePlanService, PatientService, QuestionnaireService

router = APIRouter()
security = HTTPBearer()


async def get_patient_from_token(
    db: DbSession,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Extract patient from SDK token."""
    from jose import JWTError, jwt

    from app.config import settings

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Check for SL patient ID in token
    patient_id = payload.get("sl_patient_id")
    if not patient_id:
        # Try to find patient by OW user ID
        ow_user_id = payload.get("sub")
        if not ow_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        service = PatientService(db)
        patient = service.get_by_ow_user_id(UUID(ow_user_id))
    else:
        service = PatientService(db)
        patient = service.get_by_id(UUID(patient_id))

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patient account is not active",
        )

    return patient


def _get_bp_status(systolic: int, diastolic: int) -> str:
    """Determine blood pressure status based on AHA guidelines."""
    # Normal: systolic < 120 AND diastolic < 80
    # Elevated: systolic 120-129 AND diastolic < 80
    # High (Stage 1): systolic 130-139 OR diastolic 80-89
    # High (Stage 2): systolic >= 140 OR diastolic >= 90
    if systolic >= 140 or diastolic >= 90:
        return "high"
    elif systolic >= 130 or diastolic >= 80:
        return "elevated"
    elif systolic >= 120:
        return "elevated"
    return "normal"


def _get_vital_status(value: float, vital_type: str) -> str:
    """Determine vital status based on thresholds."""
    # Simple threshold-based status
    if vital_type == "heart_rate":
        if value < 50:
            return "low"
        elif value > 100:
            return "high"
        return "normal"
    elif vital_type == "temperature":
        if value > 100.4:
            return "elevated"
        elif value > 101.5:
            return "high"
        return "normal"
    elif vital_type == "hrv":
        if value >= 50:
            return "healthy"
        elif value >= 30:
            return "fair"
        return "poor"
    elif vital_type == "resting_hr":
        if value < 50:
            return "low"
        elif value > 80:
            return "high"
        return "normal"
    return "normal"


def _get_sleep_quality(duration_minutes: int) -> str:
    """Determine sleep quality from duration."""
    hours = duration_minutes / 60
    if hours >= 7:
        return "good"
    elif hours >= 5:
        return "fair"
    return "poor"


@router.post("/summary", response_model=DashboardSummaryResponse, response_model_by_alias=True)
async def get_summary(
    db: DbSession,
    patient=Depends(get_patient_from_token),
):
    """Get patient's dashboard summary.

    Returns data in the format expected by the iOS app.
    """
    from app.models import DataSource
    from app.models.data_point_series import DataPointSeries
    from app.models.series_type_definition import SeriesTypeDefinition

    summary = patient.summary
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # ==========================================================================
    # Build Vitals
    # ==========================================================================

    # Heart Rate
    heart_rate = None
    if summary and summary.latest_heart_rate is not None and summary.latest_heart_rate_at:
        heart_rate = HeartRateSummary(
            last_reading=summary.latest_heart_rate_at,
            value_bpm=int(summary.latest_heart_rate),
            status=_get_vital_status(summary.latest_heart_rate, "heart_rate"),
        )

    # Temperature - convert from Celsius to Fahrenheit if needed
    temperature = None
    if summary and summary.latest_temperature is not None and summary.latest_temperature_at:
        temp_value = summary.latest_temperature
        # If stored in Celsius (30-45 range), convert to Fahrenheit
        if 30 <= temp_value <= 45:
            temp_value = (temp_value * 9 / 5) + 32
        temperature = TemperatureSummary(
            last_reading=summary.latest_temperature_at,
            value_fahrenheit=round(temp_value, 1),
            status=_get_vital_status(temp_value, "temperature"),
        )

    # Weight - query from data_point_series
    weight = None
    ow_user_id = patient.ow_user_id
    if ow_user_id:
        try:
            from app.models import DataSource
            from app.models.data_point_series import DataPointSeries
            from app.models.series_type_definition import SeriesTypeDefinition

            # Get latest weight
            weight_stmt = (
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
                .where(
                    DataSource.user_id == ow_user_id,
                    SeriesTypeDefinition.code.in_(["weight", "body_mass"]),
                )
                .order_by(DataPointSeries.recorded_at.desc())
                .limit(2)  # Get last 2 to calculate change
            )
            weight_records = db.execute(weight_stmt).scalars().all()

            if weight_records:
                latest = weight_records[0]
                # Convert kg to lbs (1 kg = 2.20462 lbs)
                weight_lbs = float(latest.value) * 2.20462

                # Calculate change from previous if available
                change = None
                if len(weight_records) > 1:
                    previous = weight_records[1]
                    previous_lbs = float(previous.value) * 2.20462
                    change = round(weight_lbs - previous_lbs, 1)

                weight = WeightSummary(
                    last_reading=latest.recorded_at,
                    value_lbs=round(weight_lbs, 1),
                    change_from_previous=change,
                )
        except Exception as e:
            import logging
            logging.error(f"Error fetching weight: {e}")

    # Blood Pressure - query systolic and diastolic from data_point_series
    blood_pressure = None
    if ow_user_id:
        try:
            from app.models import DataSource
            from app.models.data_point_series import DataPointSeries
            from app.models.series_type_definition import SeriesTypeDefinition

            # Get latest systolic reading
            systolic_stmt = (
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
                .where(
                    DataSource.user_id == ow_user_id,
                    SeriesTypeDefinition.code == "blood_pressure_systolic",
                )
                .order_by(DataPointSeries.recorded_at.desc())
                .limit(1)
            )
            systolic_record = db.execute(systolic_stmt).scalar_one_or_none()

            # Get latest diastolic reading
            diastolic_stmt = (
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
                .where(
                    DataSource.user_id == ow_user_id,
                    SeriesTypeDefinition.code == "blood_pressure_diastolic",
                )
                .order_by(DataPointSeries.recorded_at.desc())
                .limit(1)
            )
            diastolic_record = db.execute(diastolic_stmt).scalar_one_or_none()

            if systolic_record and diastolic_record:
                systolic = int(systolic_record.value)
                diastolic = int(diastolic_record.value)
                # Use the more recent timestamp
                last_reading = max(systolic_record.recorded_at, diastolic_record.recorded_at)
                blood_pressure = BloodPressureSummary(
                    last_reading=last_reading,
                    systolic=systolic,
                    diastolic=diastolic,
                    status=_get_bp_status(systolic, diastolic),
                )
        except Exception as e:
            import logging
            logging.error(f"Error fetching blood pressure: {e}")

    vitals = VitalsSummary(
        heart_rate=heart_rate,
        temperature=temperature,
        blood_pressure=blood_pressure,
        weight=weight,
    )

    # ==========================================================================
    # Build Recovery
    # ==========================================================================

    # Get trend data from OW tables for the patient
    ow_user_id = patient.ow_user_id

    # Sleep - query from event_record + sleep_details tables
    sleep = None
    if ow_user_id:
        from app.models.event_record import EventRecord
        from app.models.sleep_details import SleepDetails

        # Query sleep sessions for last 7 days
        sleep_stmt = (
            select(EventRecord, SleepDetails)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .outerjoin(SleepDetails, EventRecord.id == SleepDetails.record_id)
            .where(
                DataSource.user_id == ow_user_id,
                EventRecord.category == "sleep",
                EventRecord.start_datetime >= seven_days_ago,
            )
            .order_by(EventRecord.start_datetime.desc())
        )
        sleep_records = db.execute(sleep_stmt).all()

        if sleep_records:
            # Build sleep trend - group by date
            from collections import defaultdict
            daily_sleep = defaultdict(float)
            for event, details in sleep_records:
                date_str = event.start_datetime.strftime("%Y-%m-%d")
                # Use sleep_total_duration_minutes from details if available, else calculate from event
                if details and details.sleep_total_duration_minutes:
                    duration_mins = details.sleep_total_duration_minutes
                elif event.duration_seconds:
                    duration_mins = event.duration_seconds / 60
                else:
                    duration_mins = 0
                daily_sleep[date_str] += duration_mins / 60  # Convert to hours

            sleep_trend = [
                SleepTrendPoint(date=date, hours=round(hours, 1))
                for date, hours in sorted(daily_sleep.items())
            ]

            # Get most recent sleep for summary
            latest_event, latest_details = sleep_records[0]
            if latest_details and latest_details.sleep_total_duration_minutes:
                last_duration = latest_details.sleep_total_duration_minutes
            elif latest_event.duration_seconds:
                last_duration = int(latest_event.duration_seconds / 60)
            else:
                last_duration = 0

            sleep = SleepSummary(
                last_night=latest_event.start_datetime,
                duration_minutes=last_duration,
                quality=_get_sleep_quality(last_duration),
                trend=sleep_trend[-7:] if sleep_trend else [],
            )

    # HRV
    hrv = None
    if summary and summary.latest_hrv is not None and summary.latest_hrv_at:
        hrv_trend = []
        if ow_user_id:
            hrv_stmt = (
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
                .where(
                    DataSource.user_id == ow_user_id,
                    SeriesTypeDefinition.code.in_(["heart_rate_variability", "hrv"]),
                    DataPointSeries.recorded_at >= seven_days_ago,
                )
                .order_by(DataPointSeries.recorded_at.desc())
            )
            hrv_data = db.execute(hrv_stmt).scalars().all()

            from collections import defaultdict
            daily_hrv = defaultdict(list)
            for point in hrv_data:
                date_str = point.recorded_at.strftime("%Y-%m-%d")
                daily_hrv[date_str].append(float(point.value))

            hrv_trend = [
                HRVTrendPoint(date=date, value_ms=int(sum(values) / len(values)))
                for date, values in sorted(daily_hrv.items())
            ]

        hrv = HRVSummary(
            last_reading=summary.latest_hrv_at,
            average_ms=int(summary.latest_hrv),
            status=_get_vital_status(summary.latest_hrv, "hrv"),
            trend=hrv_trend[-7:] if hrv_trend else [],
        )

    # Resting Heart Rate
    resting_hr = None
    if summary and summary.latest_heart_rate is not None and summary.latest_heart_rate_at:
        rhr_trend = []
        if ow_user_id:
            rhr_stmt = (
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
                .where(
                    DataSource.user_id == ow_user_id,
                    SeriesTypeDefinition.code == "resting_heart_rate",
                    DataPointSeries.recorded_at >= seven_days_ago,
                )
                .order_by(DataPointSeries.recorded_at.desc())
            )
            rhr_data = db.execute(rhr_stmt).scalars().all()

            from collections import defaultdict
            daily_rhr = defaultdict(list)
            for point in rhr_data:
                date_str = point.recorded_at.strftime("%Y-%m-%d")
                daily_rhr[date_str].append(float(point.value))

            rhr_trend = [
                RestingHRTrendPoint(date=date, value_bpm=int(sum(values) / len(values)))
                for date, values in sorted(daily_rhr.items())
            ]

        # Use latest heart rate as resting HR approximation if no dedicated resting HR
        resting_hr = RestingHeartRateSummary(
            last_reading=summary.latest_heart_rate_at,
            value_bpm=int(summary.latest_heart_rate),
            status=_get_vital_status(summary.latest_heart_rate, "resting_hr"),
            trend=rhr_trend[-7:] if rhr_trend else None,
        )

    recovery = RecoverySummary(
        sleep=sleep,
        hrv=hrv,
        resting_heart_rate=resting_hr,
    )

    # ==========================================================================
    # Build Activity
    # ==========================================================================

    # Today's activity
    exercise_minutes = summary.today_active_minutes if summary else 0
    goal_minutes = 30  # Default goal
    progress = min(100, int((exercise_minutes or 0) / goal_minutes * 100)) if goal_minutes > 0 else 0

    today_activity = TodayActivity(
        exercise_minutes=exercise_minutes or 0,
        goal_minutes=goal_minutes,
        progress_percent=progress,
        low_intensity_minutes=0,  # TODO: Calculate from data
        moderate_intensity_minutes=exercise_minutes or 0,
        high_intensity_minutes=0,
    )

    # Weekly trend
    weekly_trend = []
    if ow_user_id:
        # Query exercise time data for last 7 days
        # Note: "exercise_time" is in minutes, not calories like "energy"
        exercise_stmt = (
            select(DataPointSeries)
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
            .where(
                DataSource.user_id == ow_user_id,
                SeriesTypeDefinition.code.in_(["exercise_time", "apple_exercise_time"]),
                DataPointSeries.recorded_at >= seven_days_ago,
            )
            .order_by(DataPointSeries.recorded_at.desc())
        )
        exercise_data = db.execute(exercise_stmt).scalars().all()

        from collections import defaultdict
        daily_exercise = defaultdict(float)
        for point in exercise_data:
            date_str = point.recorded_at.strftime("%Y-%m-%d")
            daily_exercise[date_str] += float(point.value)

        # Build weekly trend with day names
        for i in range(7):
            day = now - timedelta(days=6-i)
            date_str = day.strftime("%Y-%m-%d")
            day_name = day.strftime("%a")  # Mon, Tue, etc.
            minutes = int(daily_exercise.get(date_str, 0))
            weekly_trend.append(
                WeeklyActivityPoint(
                    day_of_week=day_name,
                    date=date_str,
                    exercise_minutes=minutes,
                )
            )

    activity = ActivitySummary(
        today=today_activity,
        weekly_trend=weekly_trend,
    )

    return DashboardSummaryResponse(
        vitals=vitals,
        recovery=recovery,
        activity=activity,
    )


@router.post("/care-plan", response_model=CarePlanResponse)
async def get_care_plan(
    db: DbSession,
    patient=Depends(get_patient_from_token),
):
    """Get patient's care plan and pending questionnaires."""
    care_plan_service = CarePlanService(db)
    questionnaire_service = QuestionnaireService(db)

    # Get active care plans
    care_plans = care_plan_service.get_active_for_patient(patient.id)

    # Parse discharge instructions
    medications = []
    activity_restrictions = []
    warning_signs = []
    follow_up_appointments = []
    emergency_contacts = []

    for plan in care_plans:
        if plan.plan_type == "discharge":
            parsed = care_plan_service.parse_discharge_content(plan)
            medications.extend(parsed.get("medications", []))
            activity_restrictions.extend(parsed.get("activity_restrictions", []))
            warning_signs.extend(parsed.get("warning_signs", []))
            follow_up_appointments.extend(parsed.get("follow_up_appointments", []))
            emergency_contacts.extend(parsed.get("emergency_contacts", []))

    # Get pending questionnaires
    pending_responses = questionnaire_service.get_pending_for_patient(patient.id)

    from sense_loop.schemas.mobile import PendingQuestionnaire, QuestionItem

    pending_questionnaires = []
    for response in pending_responses:
        questionnaire = response.questionnaire
        questions = [
            QuestionItem(
                id=q.id,
                code=q.code,
                text=q.text,
                help_text=q.help_text,
                question_type=q.question_type,
                is_required=q.is_required,
                options=q.options,
                validation=q.validation,
            )
            for q in questionnaire.questions
            if q.is_active
        ]

        pending_questionnaires.append(
            PendingQuestionnaire(
                id=response.id,
                questionnaire_id=questionnaire.id,
                title=questionnaire.title,
                description=questionnaire.description,
                due_at=response.due_at,
                questions=questions,
            )
        )

    return CarePlanResponse(
        patient_id=patient.id,
        care_plans=[
            {
                "id": str(p.id),
                "title": p.title,
                "type": p.plan_type,
                "instructions": p.instructions,
            }
            for p in care_plans
        ],
        medications=medications,
        activity_restrictions=activity_restrictions,
        warning_signs=warning_signs,
        follow_up_appointments=follow_up_appointments,
        emergency_contacts=emergency_contacts,
        pending_questionnaires=pending_questionnaires,
    )


@router.post("/questionnaire/submit", response_model=QuestionnaireSubmitResponse)
async def submit_questionnaire(
    request: QuestionnaireSubmitRequest,
    db: DbSession,
    patient=Depends(get_patient_from_token),
):
    """Submit questionnaire answers."""
    service = QuestionnaireService(db)

    # Get response
    response = service.get_response_by_id(request.response_id)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire response not found",
        )

    # Verify ownership
    if response.patient_id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit this questionnaire",
        )

    # Check status
    if response.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Questionnaire has already been submitted",
        )

    # Submit answers
    answers = [
        {
            "question_id": a.question_id,
            "value_text": a.value_text,
            "value_number": a.value_number,
            "value_boolean": a.value_boolean,
            "value_json": a.value_json,
            "skipped": a.skipped,
        }
        for a in request.answers
    ]

    response = service.submit_answers(response, answers)
    db.commit()

    return QuestionnaireSubmitResponse(
        success=True,
        response_id=response.id,
        total_score=response.total_score,
        score_interpretation=response.score_interpretation,
        message="Questionnaire submitted successfully",
    )
