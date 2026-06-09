"""Alert engine - deterministic threshold evaluation for SaMD compliance.

=== BEGIN SaMD CRITICAL SECTION ===

This module implements the core alert evaluation logic for Sense Loop.
It is designed for SaMD (Software as a Medical Device) compliance:

1. DETERMINISTIC: No ML/AI components - only explicit numeric thresholds
2. TRACEABLE: Every alert includes full protocol/rule/window traceability
3. VERSIONED: Protocols are immutable once published
4. AUDITABLE: All evaluations can be reconstructed from logged data
5. UPSERT PATTERN: One active alert per vital type per patient
   - If threshold breached + active alert exists → UPDATE
   - If threshold breached + no active alert → CREATE
   - If value normal + active alert exists → AUTO-RESOLVE

Changes to this module require:
- Design review
- Comprehensive testing
- Regulatory review for FDA 510(k) compliance

=== END SaMD CRITICAL SECTION ===
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import (
    Alert,
    AlertProtocol,
    AlertProtocolRule,
    AlertRiskWindow,
    Patient,
)

logger = logging.getLogger(__name__)


class AlertAction(str, Enum):
    """Action taken during alert evaluation."""

    CREATED = "created"
    UPDATED = "updated"
    RESOLVED = "resolved"
    NONE = "none"


@dataclass
class AlertEvaluationResult:
    """Result of alert evaluation."""

    action: AlertAction
    alert: Alert | None = None
    reason: str | None = None


class AlertEngine:
    """Deterministic alert evaluation engine."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_observation(
        self,
        patient_id: UUID,
        vital_type: str,
        value: float,
        observed_at: datetime,
        provider: str | None = None,
        context: str | None = None,  # resting, active, sleeping, post_exercise
    ) -> Alert | None:
        """Evaluate a single observation against alert protocols.

        This is the main entry point for alert evaluation.
        Called by the data hooks when new vital data arrives.

        Implements upsert pattern (matching Medplum observation-handler-bot):
        - One active alert per vital type per patient
        - If threshold breached + active alert exists → UPDATE
        - If threshold breached + no active alert → CREATE
        - If value normal + active alert exists → AUTO-RESOLVE

        Args:
            patient_id: The patient's ID
            vital_type: Type of vital (heart_rate, spo2, etc.)
            value: The observed value
            observed_at: When the observation was recorded
            provider: Data provider (whoop, oura, etc.)
            context: Activity context if known

        Returns:
            Alert if created or updated, None otherwise
        """
        result = self.evaluate_observation_detailed(
            patient_id=patient_id,
            vital_type=vital_type,
            value=value,
            observed_at=observed_at,
            provider=provider,
            context=context,
        )
        return result.alert

    def evaluate_observation_detailed(
        self,
        patient_id: UUID,
        vital_type: str,
        value: float,
        observed_at: datetime,
        provider: str | None = None,
        context: str | None = None,
    ) -> AlertEvaluationResult:
        """Evaluate observation with detailed result including action taken.

        Returns:
            AlertEvaluationResult with action (created/updated/resolved/none) and alert
        """
        # Load patient with protocol
        patient = self._get_patient(patient_id)
        if not patient:
            logger.warning("Patient %s not found for alert evaluation", patient_id)
            return AlertEvaluationResult(action=AlertAction.NONE, reason="Patient not found")

        if not patient.is_monitoring_active:
            return AlertEvaluationResult(action=AlertAction.NONE, reason="Monitoring not active")

        # Get protocol
        protocol = patient.alert_protocol
        if not protocol:
            protocol = self._get_default_protocol()
            if not protocol:
                logger.warning("No alert protocol available for patient %s", patient_id)
                return AlertEvaluationResult(action=AlertAction.NONE, reason="No protocol")

        # Calculate days post-surgery
        days_post_surgery = patient.days_post_surgery

        # Find applicable risk window
        risk_window = self._find_risk_window(protocol, days_post_surgery)

        # Find applicable rule
        rule = self._find_applicable_rule(protocol, vital_type, context)
        if not rule:
            return AlertEvaluationResult(action=AlertAction.NONE, reason="No rule for vital type")

        # Convert temperature from Celsius to Fahrenheit if needed
        if vital_type == "temperature" and 30 <= value <= 45:
            value = (value * 9 / 5) + 32
            logger.debug("Converted temperature from Celsius to Fahrenheit: %.1f°F", value)

        # Get effective thresholds
        thresholds = self._get_effective_thresholds(rule, patient, risk_window)

        # Evaluate against thresholds
        threshold_result = self._evaluate_thresholds(value, thresholds)

        # Find existing active alert for this vital type
        existing_alert = self._find_active_alert(patient_id, vital_type)

        if threshold_result:
            # Threshold breached
            threshold_breached, threshold_value, severity = threshold_result

            if existing_alert:
                # UPDATE existing alert
                updated_alert = self._update_alert(
                    alert=existing_alert,
                    observed_value=value,
                    threshold_breached=threshold_breached,
                    threshold_value=threshold_value,
                    severity=severity,
                    observed_at=observed_at,
                    rule=rule,
                    risk_window=risk_window,
                )
                logger.info(
                    "Updated alert %s for patient %s: %s %s (value: %s, threshold: %s)",
                    updated_alert.id,
                    patient_id,
                    vital_type,
                    threshold_breached,
                    value,
                    threshold_value,
                )
                return AlertEvaluationResult(action=AlertAction.UPDATED, alert=updated_alert)
            else:
                # Check cooldown for recently resolved alerts (prevent flapping)
                if self._is_in_resolution_cooldown(patient_id, vital_type, rule.cooldown_minutes):
                    logger.debug(
                        "Alert for patient %s vital %s in resolution cooldown",
                        patient_id,
                        vital_type,
                    )
                    return AlertEvaluationResult(
                        action=AlertAction.NONE, reason="In resolution cooldown"
                    )

                # CREATE new alert
                alert = self._create_alert(
                    patient=patient,
                    protocol=protocol,
                    rule=rule,
                    risk_window=risk_window,
                    vital_type=vital_type,
                    observed_value=value,
                    threshold_breached=threshold_breached,
                    threshold_value=threshold_value,
                    severity=severity,
                    observed_at=observed_at,
                    days_post_surgery=days_post_surgery,
                    context=context,
                )
                logger.info(
                    "Created alert %s for patient %s: %s %s (value: %s, threshold: %s)",
                    alert.id,
                    patient_id,
                    vital_type,
                    threshold_breached,
                    value,
                    threshold_value,
                )
                return AlertEvaluationResult(action=AlertAction.CREATED, alert=alert)

        else:
            # No threshold breached - value is normal
            if existing_alert:
                # AUTO-RESOLVE the alert
                resolved_alert = self._resolve_alert(existing_alert, value, observed_at)
                logger.info(
                    "Auto-resolved alert %s for patient %s: %s value returned to normal (%s)",
                    resolved_alert.id,
                    patient_id,
                    vital_type,
                    value,
                )
                return AlertEvaluationResult(action=AlertAction.RESOLVED, alert=resolved_alert)
            else:
                return AlertEvaluationResult(action=AlertAction.NONE, reason="No threshold breached")

    def _get_patient(self, patient_id: UUID) -> Patient | None:
        """Load patient with protocol."""
        stmt = (
            select(Patient)
            .where(Patient.id == patient_id)
            .options(
                joinedload(Patient.alert_protocol).joinedload(AlertProtocol.rules),
                joinedload(Patient.alert_protocol).joinedload(AlertProtocol.risk_windows),
                joinedload(Patient.organization),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def _get_default_protocol(self) -> AlertProtocol | None:
        """Get the default system protocol."""
        stmt = (
            select(AlertProtocol)
            .where(
                AlertProtocol.organization_id.is_(None),
                AlertProtocol.status == "published",
            )
            .options(
                joinedload(AlertProtocol.rules),
                joinedload(AlertProtocol.risk_windows),
            )
            .order_by(AlertProtocol.version.desc())
            .limit(1)
        )
        protocol = self.db.execute(stmt).unique().scalar_one_or_none()
        logger.info(
            "Default protocol lookup: found=%s, id=%s",
            protocol is not None,
            protocol.id if protocol else None,
        )
        return protocol

    def _find_risk_window(
        self, protocol: AlertProtocol, days_post_surgery: int | None
    ) -> AlertRiskWindow | None:
        """Find the applicable risk window for the current day."""
        if days_post_surgery is None:
            return None

        for window in protocol.risk_windows:
            if window.start_day <= days_post_surgery:
                if window.end_day is None or days_post_surgery <= window.end_day:
                    return window

        return None

    def _find_applicable_rule(
        self,
        protocol: AlertProtocol,
        vital_type: str,
        context: str | None,
    ) -> AlertProtocolRule | None:
        """Find the most specific applicable rule."""
        matching_rules = []

        for rule in protocol.rules:
            if not rule.is_active:
                continue
            if rule.vital_type != vital_type:
                continue

            # Check context match
            if rule.context:
                if rule.context == "any" or rule.context == context:
                    matching_rules.append(rule)
            else:
                # No context requirement
                matching_rules.append(rule)

        if not matching_rules:
            return None

        # Return highest priority rule (lowest priority number)
        return min(matching_rules, key=lambda r: r.priority)

    def _get_effective_thresholds(
        self,
        rule: AlertProtocolRule,
        patient: Patient,
        risk_window: AlertRiskWindow | None,
    ) -> dict[str, float | None]:
        """Calculate effective thresholds considering overrides."""
        thresholds = {
            "high_critical": rule.high_critical,
            "high_warning": rule.high_warning,
            "low_warning": rule.low_warning,
            "low_critical": rule.low_critical,
        }

        # Apply risk window adjustments
        if risk_window and risk_window.threshold_adjustments:
            adjustments = risk_window.threshold_adjustments.get(rule.vital_type, {})
            for key in thresholds:
                adj_key = f"{key}_adjustment"
                if adj_key in adjustments and thresholds[key] is not None:
                    thresholds[key] = thresholds[key] + adjustments[adj_key]

        # Apply patient custom thresholds
        if patient.custom_thresholds:
            patient_thresholds = patient.custom_thresholds.get(rule.vital_type, {})
            for key in thresholds:
                if key in patient_thresholds:
                    thresholds[key] = patient_thresholds[key]

        return thresholds

    def _evaluate_thresholds(
        self, value: float, thresholds: dict[str, float | None]
    ) -> tuple[str, float, str] | None:
        """Evaluate value against thresholds.

        Returns:
            Tuple of (threshold_breached, threshold_value, severity) or None
        """
        # Check in order of severity (most severe first)
        if thresholds["high_critical"] is not None and value >= thresholds["high_critical"]:
            return "high_critical", thresholds["high_critical"], "critical"

        if thresholds["low_critical"] is not None and value <= thresholds["low_critical"]:
            return "low_critical", thresholds["low_critical"], "critical"

        if thresholds["high_warning"] is not None and value >= thresholds["high_warning"]:
            return "high_warning", thresholds["high_warning"], "warning"

        if thresholds["low_warning"] is not None and value <= thresholds["low_warning"]:
            return "low_warning", thresholds["low_warning"], "warning"

        return None

    def _find_active_alert(
        self, patient_id: UUID, vital_type: str
    ) -> Alert | None:
        """Find existing active alert for this patient and vital type.

        This implements the upsert pattern - one active alert per vital type.
        """
        stmt = select(Alert).where(
            and_(
                Alert.patient_id == patient_id,
                Alert.vital_type == vital_type,
                Alert.status.in_(["active", "acknowledged"]),
            )
        ).order_by(Alert.triggered_at.desc()).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def _is_in_resolution_cooldown(
        self, patient_id: UUID, vital_type: str, cooldown_minutes: int
    ) -> bool:
        """Check if there's a recently resolved alert for this vital type.

        Prevents alert flapping (rapid create/resolve/create cycles).
        Only applies AFTER an alert has been resolved.
        """
        cooldown_start = datetime.utcnow() - timedelta(minutes=cooldown_minutes)

        stmt = select(Alert).where(
            and_(
                Alert.patient_id == patient_id,
                Alert.vital_type == vital_type,
                Alert.status == "auto_resolved",
                Alert.resolved_at >= cooldown_start,
            )
        )
        recent_resolved = self.db.execute(stmt).scalar_one_or_none()
        return recent_resolved is not None

    def _update_alert(
        self,
        alert: Alert,
        observed_value: float,
        threshold_breached: str,
        threshold_value: float,
        severity: str,
        observed_at: datetime,
        rule: AlertProtocolRule,
        risk_window: AlertRiskWindow | None,
    ) -> Alert:
        """Update an existing alert with new observation data.

        Updates the alert to reflect the latest breach while preserving
        the original trigger time for SaMD traceability.
        """
        # Update to most severe status
        if severity == "critical" and alert.severity != "critical":
            alert.severity = severity

        # Update observation data
        alert.observed_value = observed_value
        alert.threshold_breached = threshold_breached
        alert.threshold_value = threshold_value

        # Update rule/window if changed
        alert.rule_id = rule.id
        if risk_window:
            alert.risk_window_id = risk_window.id

        # Update message
        direction = "High" if "high" in threshold_breached else "Low"
        vital_display = alert.vital_type.replace("_", " ").title()
        alert.message = (
            f"Patient's {vital_display.lower()} of {observed_value} "
            f"{'exceeds' if 'high' in threshold_breached else 'is below'} "
            f"the {severity} threshold of {threshold_value}."
        )

        # Increment update count for audit trail
        if alert.data is None:
            alert.data = {}
        alert.data["update_count"] = alert.data.get("update_count", 0) + 1
        alert.data["last_update_at"] = observed_at.isoformat()

        self.db.flush()
        return alert

    def _resolve_alert(
        self,
        alert: Alert,
        resolving_value: float,
        resolved_at: datetime,
    ) -> Alert:
        """Auto-resolve an alert when the value returns to normal.

        Sets status to 'auto_resolved' to distinguish from manual resolution.
        """
        alert.status = "auto_resolved"
        alert.resolved_at = resolved_at
        alert.resolution_notes = (
            f"Auto-resolved: value returned to normal ({resolving_value})"
        )

        # Store resolving observation in data for audit
        if alert.data is None:
            alert.data = {}
        alert.data["resolving_value"] = resolving_value
        alert.data["auto_resolved"] = True

        self.db.flush()
        return alert

    def _create_alert(
        self,
        patient: Patient,
        protocol: AlertProtocol,
        rule: AlertProtocolRule,
        risk_window: AlertRiskWindow | None,
        vital_type: str,
        observed_value: float,
        threshold_breached: str,
        threshold_value: float,
        severity: str,
        observed_at: datetime,
        days_post_surgery: int | None,
        context: str | None,
    ) -> Alert:
        """Create an alert with full traceability."""
        # Build alert title
        direction = "High" if "high" in threshold_breached else "Low"
        vital_display = vital_type.replace("_", " ").title()
        title = f"{direction} {vital_display} Alert"

        # Build message
        message = (
            f"Patient's {vital_display.lower()} of {observed_value} "
            f"{'exceeds' if 'high' in threshold_breached else 'is below'} "
            f"the {severity} threshold of {threshold_value}."
        )

        alert = Alert(
            id=uuid4(),
            patient_id=patient.id,
            organization_id=patient.organization_id,
            title=title,
            message=message,
            severity=severity,
            category="vital_sign",
            status="active",
            triggered_at=observed_at,
            # SaMD Traceability
            protocol_id=protocol.id,
            protocol_version=protocol.version,
            rule_id=rule.id,
            risk_window_id=risk_window.id if risk_window else None,
            days_post_surgery=days_post_surgery,
            patient_context=context,
            vital_type=vital_type,
            observed_value=observed_value,
            threshold_breached=threshold_breached,
            threshold_value=threshold_value,
        )

        self.db.add(alert)
        self.db.flush()

        return alert
