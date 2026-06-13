"""Tests for AlertEngine upsert pattern.

Tests verify the Medplum-style upsert behavior:
- One active alert per vital type per patient
- If threshold breached + active alert exists -> UPDATE
- If threshold breached + no active alert -> CREATE
- If value normal + active alert exists -> AUTO-RESOLVE
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from sense_loop.services.alert_engine import (
    AlertAction,
    AlertEngine,
    AlertEvaluationResult,
)


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


@pytest.fixture
def mock_organization():
    """Create a mock organization."""
    org = MagicMock()
    org.id = uuid4()
    org.name = "Test Hospital"
    return org


@pytest.fixture
def mock_patient(mock_organization):
    """Create a mock patient with monitoring active."""
    patient = MagicMock()
    patient.id = uuid4()
    patient.organization_id = mock_organization.id
    patient.organization = mock_organization
    patient.is_monitoring_active = True
    patient.alert_protocol = None
    patient.days_post_surgery = 5
    patient.custom_thresholds = None
    return patient


@pytest.fixture
def mock_protocol():
    """Create a mock alert protocol."""
    protocol = MagicMock()
    protocol.id = uuid4()
    protocol.version = 1
    protocol.status = "published"
    protocol.rules = []
    protocol.risk_windows = []
    return protocol


@pytest.fixture
def mock_rule():
    """Create a mock protocol rule for heart rate."""
    rule = MagicMock()
    rule.id = uuid4()
    rule.vital_type = "heart_rate"
    rule.is_active = True
    rule.context = None
    rule.priority = 1
    rule.high_critical = 120
    rule.high_warning = 100
    rule.low_warning = 50
    rule.low_critical = 40
    rule.cooldown_minutes = 15
    return rule


@pytest.fixture
def mock_existing_alert():
    """Create a mock existing active alert."""
    alert = MagicMock()
    alert.id = uuid4()
    alert.vital_type = "heart_rate"
    alert.status = "active"
    alert.severity = "warning"
    alert.observed_value = 105
    alert.threshold_breached = "high_warning"
    alert.threshold_value = 100
    alert.triggered_at = datetime.utcnow() - timedelta(hours=1)
    alert.data = {}
    return alert


class TestAlertAction:
    """Tests for AlertAction enum."""

    def test_action_values(self):
        """Test all action types are defined."""
        assert AlertAction.CREATED == "created"
        assert AlertAction.UPDATED == "updated"
        assert AlertAction.RESOLVED == "resolved"
        assert AlertAction.NONE == "none"


class TestAlertEvaluationResult:
    """Tests for AlertEvaluationResult dataclass."""

    def test_result_with_alert(self):
        """Test result with alert."""
        mock_alert = MagicMock()
        result = AlertEvaluationResult(
            action=AlertAction.CREATED,
            alert=mock_alert,
        )
        assert result.action == AlertAction.CREATED
        assert result.alert == mock_alert
        assert result.reason is None

    def test_result_without_alert(self):
        """Test result without alert."""
        result = AlertEvaluationResult(
            action=AlertAction.NONE,
            reason="No threshold breached",
        )
        assert result.action == AlertAction.NONE
        assert result.alert is None
        assert result.reason == "No threshold breached"


class TestAlertEngineUpsertPattern:
    """Tests for AlertEngine upsert behavior."""

    def test_create_new_alert_when_threshold_breached(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule
    ):
        """Test CREATE: threshold breached with no existing alert."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=125,  # Above high_critical (120)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.CREATED
        assert result.alert is not None
        mock_db_session.add.assert_called_once()

    def test_update_existing_alert_when_threshold_still_breached(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test UPDATE: threshold breached with existing active alert."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=130,  # Still above threshold
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.UPDATED
        assert result.alert == mock_existing_alert
        # Should NOT create new alert
        mock_db_session.add.assert_not_called()

    def test_auto_resolve_alert_when_value_normal(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test AUTO-RESOLVE: value normal with existing active alert."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=75,  # Normal range
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.RESOLVED
        assert result.alert == mock_existing_alert
        assert mock_existing_alert.status == "auto_resolved"
        assert mock_existing_alert.resolved_at is not None

    def test_no_action_when_value_normal_no_alert(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule
    ):
        """Test NONE: value normal with no existing alert."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=75,  # Normal range
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.NONE
        assert result.alert is None
        assert result.reason == "No threshold breached"

    def test_severity_escalation_on_update(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test that severity escalates from warning to critical on update."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]
        mock_existing_alert.severity = "warning"

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=125,  # Above high_critical (120)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.UPDATED
        assert mock_existing_alert.severity == "critical"


class TestAlertEngineEdgeCases:
    """Tests for AlertEngine edge cases."""

    def test_patient_not_found(self, mock_db_session):
        """Test handling when patient not found."""
        engine = AlertEngine(mock_db_session)

        with patch.object(engine, "_get_patient", return_value=None):
            result = engine.evaluate_observation_detailed(
                patient_id=uuid4(),
                vital_type="heart_rate",
                value=125,
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.NONE
        assert result.reason == "Patient not found"

    def test_monitoring_not_active(self, mock_db_session, mock_patient):
        """Test handling when patient monitoring is not active."""
        engine = AlertEngine(mock_db_session)
        mock_patient.is_monitoring_active = False

        with patch.object(engine, "_get_patient", return_value=mock_patient):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=125,
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.NONE
        assert result.reason == "Monitoring not active"

    def test_no_protocol_available(self, mock_db_session, mock_patient):
        """Test handling when no protocol is available."""
        engine = AlertEngine(mock_db_session)
        mock_patient.alert_protocol = None

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=125,
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.NONE
        assert result.reason == "No protocol"

    def test_no_rule_for_vital_type(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test handling when no rule exists for vital type."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = []  # No rules

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="unknown_vital",
                value=125,
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.NONE
        assert result.reason == "No rule for vital type"


class TestAlertEngineUpdateCount:
    """Tests for alert update tracking."""

    def test_update_increments_count(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test that update count is incremented on each update."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]
        mock_existing_alert.data = {"update_count": 3}

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=130,
                observed_at=datetime.utcnow(),
            )

        assert mock_existing_alert.data["update_count"] == 4

    def test_first_update_initializes_count(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test that first update initializes update_count to 1."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]
        mock_existing_alert.data = None

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=130,
                observed_at=datetime.utcnow(),
            )

        assert mock_existing_alert.data["update_count"] == 1


class TestAlertEngineResolveAlert:
    """Tests for alert resolution."""

    def test_resolve_sets_auto_resolved_status(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test that resolved alerts have auto_resolved status."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=75,
                observed_at=datetime.utcnow(),
            )

        assert mock_existing_alert.status == "auto_resolved"
        assert "value returned to normal" in mock_existing_alert.resolution_notes

    def test_resolve_stores_resolving_value(
        self, mock_db_session, mock_patient, mock_protocol, mock_rule, mock_existing_alert
    ):
        """Test that resolving value is stored in data."""
        engine = AlertEngine(mock_db_session)
        mock_protocol.rules = [mock_rule]
        mock_existing_alert.data = None

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=mock_existing_alert),
        ):
            engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="heart_rate",
                value=75,
                observed_at=datetime.utcnow(),
            )

        assert mock_existing_alert.data["resolving_value"] == 75
        assert mock_existing_alert.data["auto_resolved"] is True


class TestAlertEngineTemperatureConversion:
    """Tests for temperature unit conversion."""

    def test_celsius_converted_to_fahrenheit(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that Celsius temperatures are converted to Fahrenheit."""
        engine = AlertEngine(mock_db_session)

        # Create rule for temperature
        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "temperature"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = 102  # Fahrenheit
        rule.high_warning = 100
        rule.low_warning = 96
        rule.low_critical = 94
        rule.cooldown_minutes = 15
        mock_protocol.rules = [rule]

        # Pass 38C which should convert to ~100.4F
        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="temperature",
                value=38,  # Celsius
                observed_at=datetime.utcnow(),
            )

        # 38C = 100.4F which triggers high_warning threshold
        assert result.action == AlertAction.CREATED

    def test_normal_celsius_no_alert(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that normal Celsius temperature does not trigger alert."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "temperature"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = 102
        rule.high_warning = 100
        rule.low_warning = 96
        rule.low_critical = 94
        rule.cooldown_minutes = 15
        mock_protocol.rules = [rule]

        # Pass 37C which should convert to ~98.6F (normal)
        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="temperature",
                value=37,  # Celsius - normal
                observed_at=datetime.utcnow(),
            )

        # 37C = 98.6F which is normal (between 96 and 100)
        assert result.action == AlertAction.NONE
        assert result.reason == "No threshold breached"

    def test_temperature_auto_resolve_after_normal(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that temperature alert auto-resolves when temp returns to normal."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "temperature"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = 102
        rule.high_warning = 100
        rule.low_warning = 96
        rule.low_critical = 94
        rule.cooldown_minutes = 15
        mock_protocol.rules = [rule]

        # Existing high temp alert
        existing_alert = MagicMock()
        existing_alert.id = uuid4()
        existing_alert.vital_type = "temperature"
        existing_alert.status = "active"
        existing_alert.severity = "critical"
        existing_alert.data = {}

        # Pass 37C which should convert to ~98.6F (normal) and resolve alert
        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="temperature",
                value=37,  # Celsius - normal
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.RESOLVED
        assert existing_alert.status == "auto_resolved"


class TestAlertEngineLowThresholds:
    """Tests for low threshold breaches."""

    def test_low_spo2_creates_alert(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that low SpO2 creates an alert."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "spo2"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = None
        rule.high_warning = None
        rule.low_warning = 94
        rule.low_critical = 90
        rule.cooldown_minutes = 30
        mock_protocol.rules = [rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="spo2",
                value=92,  # Below low_warning (94)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.CREATED

    def test_critical_low_spo2(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that critically low SpO2 creates critical alert."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "spo2"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = None
        rule.high_warning = None
        rule.low_warning = 94
        rule.low_critical = 90
        rule.cooldown_minutes = 30
        mock_protocol.rules = [rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="spo2",
                value=88,  # Below low_critical (90)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.CREATED
        # Check the alert was created with critical severity
        assert result.alert is not None

    def test_normal_spo2_resolves_alert(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that normal SpO2 resolves existing alert."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "spo2"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = None
        rule.high_warning = None
        rule.low_warning = 94
        rule.low_critical = 90
        rule.cooldown_minutes = 30
        mock_protocol.rules = [rule]

        existing_alert = MagicMock()
        existing_alert.id = uuid4()
        existing_alert.vital_type = "spo2"
        existing_alert.status = "active"
        existing_alert.severity = "warning"
        existing_alert.data = {}

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="spo2",
                value=98,  # Normal (above 94)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.RESOLVED
        assert existing_alert.status == "auto_resolved"


class TestAlertEngineBloodPressure:
    """Tests for blood pressure alerts."""

    def test_high_systolic_bp_creates_alert(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that high systolic BP creates an alert."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "blood_pressure_systolic"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = 180
        rule.high_warning = 160
        rule.low_warning = 90
        rule.low_critical = 80
        rule.cooldown_minutes = 30
        mock_protocol.rules = [rule]

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=None),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="blood_pressure_systolic",
                value=170,  # Above high_warning (160)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.CREATED

    def test_normal_bp_resolves_alert(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that normal BP resolves existing alert."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "blood_pressure_systolic"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = 180
        rule.high_warning = 160
        rule.low_warning = 90
        rule.low_critical = 80
        rule.cooldown_minutes = 30
        mock_protocol.rules = [rule]

        existing_alert = MagicMock()
        existing_alert.id = uuid4()
        existing_alert.vital_type = "blood_pressure_systolic"
        existing_alert.status = "active"
        existing_alert.severity = "warning"
        existing_alert.data = {}

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="blood_pressure_systolic",
                value=125,  # Normal (between 90 and 160)
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.RESOLVED
        assert existing_alert.status == "auto_resolved"

    def test_bp_update_not_create_duplicate(
        self, mock_db_session, mock_patient, mock_protocol
    ):
        """Test that subsequent high BP updates existing alert, not creates new."""
        engine = AlertEngine(mock_db_session)

        rule = MagicMock()
        rule.id = uuid4()
        rule.vital_type = "blood_pressure_systolic"
        rule.is_active = True
        rule.context = None
        rule.priority = 1
        rule.high_critical = 180
        rule.high_warning = 160
        rule.low_warning = 90
        rule.low_critical = 80
        rule.cooldown_minutes = 30
        mock_protocol.rules = [rule]

        existing_alert = MagicMock()
        existing_alert.id = uuid4()
        existing_alert.vital_type = "blood_pressure_systolic"
        existing_alert.status = "active"
        existing_alert.severity = "warning"
        existing_alert.observed_value = 165
        existing_alert.data = {"update_count": 2}

        with (
            patch.object(engine, "_get_patient", return_value=mock_patient),
            patch.object(engine, "_get_default_protocol", return_value=mock_protocol),
            patch.object(engine, "_find_active_alert", return_value=existing_alert),
        ):
            result = engine.evaluate_observation_detailed(
                patient_id=mock_patient.id,
                vital_type="blood_pressure_systolic",
                value=175,  # Still high
                observed_at=datetime.utcnow(),
            )

        assert result.action == AlertAction.UPDATED
        assert result.alert == existing_alert
        assert existing_alert.data["update_count"] == 3
        mock_db_session.add.assert_not_called()
