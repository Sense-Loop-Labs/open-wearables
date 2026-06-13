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
        """Check if any answers should trigger alerts."""
        from sense_loop.services.alert_engine import AlertEngine

        for answer in response.answers:
            if answer.skipped:
                continue

            question = answer.question
            if not question.alert_config:
                continue

            trigger_values = question.alert_config.get("trigger_values", [])
            answer_value = (
                answer.value_text
                or str(answer.value_number)
                or str(answer.value_boolean)
            )

            if answer_value in trigger_values:
                # This answer triggers an alert
                self._create_questionnaire_alert(response, question, answer)

    def _create_questionnaire_alert(
        self,
        response: QuestionnaireResponse,
        question: QuestionnaireQuestion,
        answer: QuestionnaireAnswer,
    ) -> None:
        """Create an alert from a questionnaire answer."""
        from sense_loop.models import Alert, Patient

        # Get patient
        stmt = select(Patient).where(Patient.id == response.patient_id)
        patient = self.db.execute(stmt).scalar_one_or_none()
        if not patient:
            return

        alert_config = question.alert_config
        severity = alert_config.get("alert_severity", "warning")
        message = alert_config.get(
            "alert_message",
            f"Patient response requires attention: {question.text}",
        )

        alert = Alert(
            id=uuid4(),
            patient_id=patient.id,
            organization_id=patient.organization_id,
            title=f"Questionnaire Alert: {question.code}",
            message=message,
            severity=severity,
            category="questionnaire",
            status="active",
            triggered_at=datetime.utcnow(),
            data={
                "questionnaire_id": str(response.questionnaire_id),
                "response_id": str(response.id),
                "question_id": str(question.id),
                "question_code": question.code,
                "answer_value": answer.value_text
                or answer.value_number
                or answer.value_boolean,
            },
        )

        self.db.add(alert)
        self.db.flush()

        logger.info(
            "Created questionnaire alert %s for patient %s from question %s",
            alert.id,
            patient.id,
            question.code,
        )
