"""Questionnaire service - questionnaire and response management."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import (
    Questionnaire,
    QuestionnaireAnswer,
    QuestionnaireQuestion,
    QuestionnaireResponse,
)

logger = logging.getLogger(__name__)


class QuestionnaireService:
    """Service for managing questionnaires and responses."""

    def __init__(self, db: Session):
        self.db = db

    def get_questionnaire_by_id(self, questionnaire_id: UUID) -> Questionnaire | None:
        """Get questionnaire by ID with questions."""
        stmt = (
            select(Questionnaire)
            .where(Questionnaire.id == questionnaire_id)
            .options(joinedload(Questionnaire.questions))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_response_by_id(self, response_id: UUID) -> QuestionnaireResponse | None:
        """Get response by ID with answers."""
        stmt = (
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.id == response_id)
            .options(
                joinedload(QuestionnaireResponse.questionnaire).joinedload(
                    Questionnaire.questions
                ),
                joinedload(QuestionnaireResponse.answers),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_pending_for_patient(self, patient_id: UUID) -> list[QuestionnaireResponse]:
        """Get pending (not completed) questionnaire responses for a patient."""
        stmt = (
            select(QuestionnaireResponse)
            .where(
                QuestionnaireResponse.patient_id == patient_id,
                QuestionnaireResponse.status.in_(["in_progress"]),
            )
            .options(
                joinedload(QuestionnaireResponse.questionnaire).joinedload(
                    Questionnaire.questions
                ),
            )
            .order_by(QuestionnaireResponse.due_at.asc().nullslast())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def list_responses_for_patient(
        self,
        patient_id: UUID,
        *,
        status: str | None = None,
        questionnaire_id: UUID | None = None,
        limit: int = 50,
    ) -> list[QuestionnaireResponse]:
        """List questionnaire responses for a patient."""
        stmt = (
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.patient_id == patient_id)
            .options(
                joinedload(QuestionnaireResponse.questionnaire),
                joinedload(QuestionnaireResponse.answers),
            )
        )

        if status:
            stmt = stmt.where(QuestionnaireResponse.status == status)

        if questionnaire_id:
            stmt = stmt.where(
                QuestionnaireResponse.questionnaire_id == questionnaire_id
            )

        stmt = stmt.order_by(QuestionnaireResponse.created_at.desc()).limit(limit)

        return list(self.db.execute(stmt).unique().scalars().all())

    def create_response(
        self,
        patient_id: UUID,
        questionnaire_id: UUID,
        *,
        scheduled_for: datetime | None = None,
        due_at: datetime | None = None,
    ) -> QuestionnaireResponse:
        """Create a new questionnaire response for a patient."""
        response = QuestionnaireResponse(
            id=uuid4(),
            patient_id=patient_id,
            questionnaire_id=questionnaire_id,
            status="in_progress",
            scheduled_for=scheduled_for,
            due_at=due_at,
        )

        self.db.add(response)
        self.db.flush()

        logger.info(
            "Created questionnaire response %s for patient %s",
            response.id,
            patient_id,
        )
        return response

    def submit_answers(
        self,
        response: QuestionnaireResponse,
        answers: list[dict],
    ) -> QuestionnaireResponse:
        """Submit answers for a questionnaire response.

        Args:
            response: The questionnaire response
            answers: List of answer dicts with question_id and value fields
        """
        questionnaire = response.questionnaire

        # Process each answer
        total_score = 0.0
        scored_count = 0

        for answer_data in answers:
            question_id = answer_data.get("question_id")
            if not question_id:
                continue

            # Find the question
            question = self._get_question(question_id)
            if not question:
                logger.warning("Question %s not found", question_id)
                continue

            # Create answer
            answer = QuestionnaireAnswer(
                id=uuid4(),
                response_id=response.id,
                question_id=question_id,
                value_text=answer_data.get("value_text"),
                value_number=answer_data.get("value_number"),
                value_boolean=answer_data.get("value_boolean"),
                value_json=answer_data.get("value_json"),
                skipped=answer_data.get("skipped", False),
            )

            # Calculate score if applicable
            if questionnaire.has_scoring and not answer.skipped:
                score = self._calculate_answer_score(question, answer)
                if score is not None:
                    answer.score = score
                    total_score += score
                    scored_count += 1

            self.db.add(answer)

        # Update response
        response.status = "completed"
        response.completed_at = datetime.utcnow()

        if questionnaire.has_scoring and scored_count > 0:
            response.total_score = total_score
            response.score_interpretation = self._interpret_score(
                questionnaire, total_score
            )

        self.db.flush()

        # Reload response with answers and questions for alert checking
        self.db.refresh(response)
        response = self.db.execute(
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.id == response.id)
            .options(
                joinedload(QuestionnaireResponse.answers).joinedload(QuestionnaireAnswer.question)
            )
        ).unique().scalar_one()

        # Check for alert triggers
        self._check_alert_triggers(response)

        # Trigger task completion check for questionnaire-based tasks
        self._trigger_task_completion(response)

        logger.info(
            "Submitted %d answers for response %s (score: %s)",
            len(answers),
            response.id,
            response.total_score,
        )

        return response

    def _trigger_task_completion(self, response: QuestionnaireResponse) -> None:
        """Trigger task completion check for questionnaire-based tasks."""
        try:
            from app.integrations.celery.tasks.instruction_tasks import (
                process_questionnaire_for_tasks,
            )

            questionnaire = response.questionnaire

            process_questionnaire_for_tasks.delay(
                patient_id=str(response.patient_id),
                questionnaire_code=questionnaire.code if questionnaire else "unknown",
                response_id=str(response.id),
                submitted_at=response.completed_at.isoformat() if response.completed_at else datetime.utcnow().isoformat(),
            )

            logger.debug(
                "Triggered task completion check for questionnaire %s",
                response.id,
            )

        except Exception as e:
            # Don't fail the main submission if task completion fails
            logger.warning(
                "Failed to trigger task completion for questionnaire: %s", str(e)
            )

    def _get_question(self, question_id: UUID) -> QuestionnaireQuestion | None:
        """Get a question by ID."""
        stmt = select(QuestionnaireQuestion).where(
            QuestionnaireQuestion.id == question_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _calculate_answer_score(
        self,
        question: QuestionnaireQuestion,
        answer: QuestionnaireAnswer,
    ) -> float | None:
        """Calculate score for an answer."""
        if not question.options:
            # For numeric questions, use the value directly
            if answer.value_number is not None:
                weight = question.score_weight or 1.0
                return answer.value_number * weight
            return None

        # For choice questions, look up the option score
        answer_value = answer.value_text or str(answer.value_number) or ""

        for option in question.options:
            if option.get("value") == answer_value:
                option_score = option.get("score")
                if option_score is not None:
                    weight = question.score_weight or 1.0
                    return float(option_score) * weight

        return None

    def _interpret_score(
        self,
        questionnaire: Questionnaire,
        total_score: float,
    ) -> str | None:
        """Interpret the total score using questionnaire config."""
        if not questionnaire.scoring_config:
            return None

        ranges = questionnaire.scoring_config.get("ranges", [])
        for range_def in ranges:
            min_val = range_def.get("min", float("-inf"))
            max_val = range_def.get("max", float("inf"))
            if min_val <= total_score <= max_val:
                return range_def.get("label")

        return None

    def _check_alert_triggers(self, response: QuestionnaireResponse) -> None:
        """Check answers for concerns and update alerts + patient summary."""
        from sense_loop.models import Alert, Patient, PatientSummary

        # Get patient
        stmt = select(Patient).where(Patient.id == response.patient_id)
        patient = self.db.execute(stmt).scalar_one_or_none()
        if not patient:
            return

        # Resolve all previous questionnaire alerts for this patient
        self._resolve_previous_questionnaire_alerts(response.patient_id)

        # Collect all concerns from this response
        concerns: list[dict] = []

        for answer in response.answers:
            if answer.skipped:
                continue

            question = answer.question
            if not question or not question.alert_config:
                continue

            trigger_values = question.alert_config.get("trigger_values", [])
            severity_by_value = question.alert_config.get("severity_by_value", {})
            default_severity = question.alert_config.get("alert_severity", "warning")
            alert_on_any_value = question.alert_config.get("alert_on_any_value", False)

            # Collect all answer values to check
            values_to_check = []

            # Check value_json for multi-choice answers
            if answer.value_json:
                selected = answer.value_json.get("selected", [])
                if isinstance(selected, list):
                    values_to_check.extend(selected)
                else:
                    values_to_check.append(selected)

            # Check other value fields
            if answer.value_text:
                values_to_check.append(answer.value_text)
            if answer.value_number is not None:
                values_to_check.append(answer.value_number)
                values_to_check.append(str(answer.value_number))
            if answer.value_boolean is not None:
                values_to_check.append(answer.value_boolean)
                values_to_check.append(str(answer.value_boolean))  # 'True' or 'False'
                values_to_check.append(str(answer.value_boolean).lower())  # 'true' or 'false'

            # Handle "alert on any value" - flag if user provided any answer
            if alert_on_any_value and values_to_check:
                # Get the display value
                if answer.value_number is not None:
                    display_text = str(answer.value_number)
                elif answer.value_text:
                    display_text = answer.value_text
                elif answer.value_boolean is not None:
                    display_text = "Yes" if answer.value_boolean else "No"
                else:
                    display_text = str(values_to_check[0])

                severity = default_severity
                if severity != "info":
                    concerns.append({
                        "question_text": question.text,
                        "question_code": question.code,
                        "answer_text": display_text,
                        "severity": severity,
                        "question_id": str(question.id),
                        "answer_id": str(answer.id),
                    })
                continue  # Skip trigger_values check for this answer

            # Check if any answer value matches a trigger
            for val in values_to_check:
                if val in trigger_values:
                    # Determine severity for this value
                    if str(val) in severity_by_value:
                        severity = severity_by_value[str(val)]
                    else:
                        severity = default_severity

                    # Skip "info" level - these are informational, not concerns
                    if severity == "info":
                        continue

                    # Format answer text for display
                    if val is True or val == "true":
                        display_text = "Yes"
                    elif val is False or val == "false":
                        display_text = "No"
                    else:
                        display_text = str(val)

                    concerns.append({
                        "question_text": question.text,
                        "question_code": question.code,
                        "answer_text": display_text,
                        "severity": severity,
                        "question_id": str(question.id),
                        "answer_id": str(answer.id),
                    })
                    break  # Only one concern per answer

        # Create alerts for each concern
        now = datetime.utcnow()
        for concern in concerns:
            alert = Alert(
                id=uuid4(),
                patient_id=patient.id,
                organization_id=patient.organization_id,
                title=f"Symptom Concern: {concern['question_code']}",
                message=f"{concern['question_text']}: {concern['answer_text']}",
                severity=concern["severity"],
                category="questionnaire",
                status="active",
                triggered_at=now,
                data={
                    "questionnaire_id": str(response.questionnaire_id),
                    "response_id": str(response.id),
                    "question_id": concern["question_id"],
                    "question_code": concern["question_code"],
                    "question_text": concern["question_text"],
                    "answer_text": concern["answer_text"],
                },
            )
            self.db.add(alert)
            logger.info(
                "Created questionnaire alert for patient %s: %s - %s (%s)",
                patient.id,
                concern["question_text"],
                concern["answer_text"],
                concern["severity"],
            )

        # Update patient summary
        self._update_patient_summary_concerns(patient.id, concerns, now)

        self.db.flush()

    def _resolve_previous_questionnaire_alerts(self, patient_id: UUID) -> None:
        """Resolve all previous active questionnaire alerts for a patient."""
        from sense_loop.models import Alert

        stmt = (
            select(Alert)
            .where(
                Alert.patient_id == patient_id,
                Alert.category == "questionnaire",
                Alert.status == "active",
            )
        )
        previous_alerts = self.db.execute(stmt).scalars().all()

        now = datetime.utcnow()
        for alert in previous_alerts:
            alert.status = "auto_resolved"
            alert.resolved_at = now
            alert.resolution_type = "new_questionnaire_response"

        if previous_alerts:
            logger.info(
                "Auto-resolved %d previous questionnaire alerts for patient %s",
                len(previous_alerts),
                patient_id,
            )

    def _update_patient_summary_concerns(
        self,
        patient_id: UUID,
        concerns: list[dict],
        response_time: datetime,
    ) -> None:
        """Update patient summary with questionnaire concerns."""
        from sense_loop.models import PatientSummary

        stmt = select(PatientSummary).where(PatientSummary.patient_id == patient_id)
        summary = self.db.execute(stmt).scalar_one_or_none()

        if not summary:
            logger.warning("No patient summary found for patient %s", patient_id)
            return

        # Determine highest severity
        highest_severity = None
        if concerns:
            severities = [c["severity"] for c in concerns]
            if "critical" in severities:
                highest_severity = "critical"
            elif "warning" in severities:
                highest_severity = "warning"

        # Update summary fields
        summary.has_questionnaire_concerns = len(concerns) > 0
        summary.questionnaire_concern_count = len(concerns)
        summary.highest_questionnaire_severity = highest_severity
        summary.questionnaire_concerns = [
            {
                "question_text": c["question_text"],
                "answer_text": c["answer_text"],
                "severity": c["severity"],
                "question_code": c["question_code"],
            }
            for c in concerns
        ] if concerns else None
        summary.last_questionnaire_response_at = response_time

        logger.info(
            "Updated patient %s summary: %d concerns, highest severity: %s",
            patient_id,
            len(concerns),
            highest_severity,
        )

    def generate_recurring_questionnaires(self) -> int:
        """Generate questionnaire responses for recurring assignments.

        Checks all active questionnaire assignments where the questionnaire
        type is 'daily' or 'weekly' and creates new responses if needed.

        Returns:
            Number of responses created
        """
        from datetime import timedelta
        from sense_loop.models import PatientQuestionnaireAssignment, Patient

        now = datetime.utcnow()
        today = now.date()
        responses_created = 0

        # Find active assignments for daily/weekly questionnaires
        stmt = (
            select(PatientQuestionnaireAssignment)
            .join(Questionnaire)
            .join(Patient)
            .where(
                PatientQuestionnaireAssignment.status == "active",
                PatientQuestionnaireAssignment.effective_start <= now,
                Patient.is_active == True,  # noqa: E712
                Questionnaire.questionnaire_type.in_(["daily", "weekly"]),
            )
            .options(
                joinedload(PatientQuestionnaireAssignment.questionnaire),
                joinedload(PatientQuestionnaireAssignment.patient),
            )
        )

        # Filter out assignments past their end date
        assignments = [
            a for a in self.db.execute(stmt).unique().scalars().all()
            if a.effective_end is None or a.effective_end >= now
        ]

        for assignment in assignments:
            questionnaire = assignment.questionnaire
            should_generate = False

            if questionnaire.questionnaire_type == "daily":
                # Generate if we haven't generated today
                if assignment.last_generated_at is None:
                    should_generate = True
                elif assignment.last_generated_at.date() < today:
                    should_generate = True

            elif questionnaire.questionnaire_type == "weekly":
                # Generate if we haven't generated this week
                if assignment.last_generated_at is None:
                    should_generate = True
                else:
                    days_since = (today - assignment.last_generated_at.date()).days
                    if days_since >= 7:
                        should_generate = True

            if should_generate:
                # Check if there's already a pending response for this questionnaire
                existing = self._get_pending_response_for_assignment(assignment)
                if existing:
                    logger.debug(
                        "Skipping generation for assignment %s - pending response exists",
                        assignment.id,
                    )
                    continue

                # Create new response
                response = self.create_response(
                    patient_id=assignment.patient_id,
                    questionnaire_id=assignment.questionnaire_id,
                )

                # Update last_generated_at
                assignment.last_generated_at = now

                responses_created += 1
                logger.info(
                    "Generated %s questionnaire response %s for patient %s",
                    questionnaire.questionnaire_type,
                    response.id,
                    assignment.patient_id,
                )

        return responses_created

    def _get_pending_response_for_assignment(
        self,
        assignment: "PatientQuestionnaireAssignment",
    ) -> QuestionnaireResponse | None:
        """Check if there's already a pending response for this assignment."""
        from sense_loop.models import PatientQuestionnaireAssignment

        stmt = (
            select(QuestionnaireResponse)
            .where(
                QuestionnaireResponse.patient_id == assignment.patient_id,
                QuestionnaireResponse.questionnaire_id == assignment.questionnaire_id,
                QuestionnaireResponse.status == "in_progress",
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def copy_for_patient(
        self,
        template_id: UUID,
        patient_id: UUID,
    ) -> Questionnaire:
        """Create a patient-specific copy of a questionnaire template.

        Args:
            template_id: ID of the template questionnaire to copy
            patient_id: ID of the patient to assign the copy to

        Returns:
            The newly created patient-specific questionnaire copy
        """
        # Get template with questions
        template = self.get_questionnaire_by_id(template_id)
        if not template:
            raise ValueError(f"Questionnaire template {template_id} not found")

        # Check if a copy already exists for this patient and template
        existing = self.db.execute(
            select(Questionnaire).where(
                Questionnaire.patient_id == patient_id,
                Questionnaire.source_template_id == template_id,
            )
        ).scalar_one_or_none()

        if existing:
            return existing

        # Create a unique code for the patient copy
        short_patient_id = str(patient_id)[:8]
        copy_code = f"{template.code}_p{short_patient_id}"

        # Create copy with patient_id set
        copy = Questionnaire(
            id=uuid4(),
            patient_id=patient_id,
            source_template_id=template_id,
            organization_id=template.organization_id,
            title=template.title,
            code=copy_code,
            description=template.description,
            questionnaire_type=template.questionnaire_type,
            category=template.category,
            estimated_minutes=template.estimated_minutes,
            allow_skip=template.allow_skip,
            require_completion=template.require_completion,
            has_scoring=template.has_scoring,
            scoring_config=template.scoring_config,
            is_active=True,
            version=1,
        )

        self.db.add(copy)
        self.db.flush()

        # Copy questions
        for q in template.questions:
            copy_question = QuestionnaireQuestion(
                id=uuid4(),
                questionnaire_id=copy.id,
                code=q.code,
                text=q.text,
                help_text=q.help_text,
                question_type=q.question_type,
                order=q.order,
                is_required=q.is_required,
                validation=q.validation,
                options=q.options,
                condition=q.condition,
                score_weight=q.score_weight,
                alert_config=q.alert_config,
                is_active=q.is_active,
            )
            self.db.add(copy_question)

        self.db.flush()

        logger.info(
            "Created patient questionnaire copy %s from template %s for patient %s",
            copy.id,
            template_id,
            patient_id,
        )

        return copy

    def get_patient_questionnaires(
        self,
        patient_id: UUID,
    ) -> list[Questionnaire]:
        """Get all patient-specific questionnaire copies for a patient."""
        stmt = (
            select(Questionnaire)
            .where(Questionnaire.patient_id == patient_id)
            .options(joinedload(Questionnaire.questions))
            .order_by(Questionnaire.created_at.desc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())
