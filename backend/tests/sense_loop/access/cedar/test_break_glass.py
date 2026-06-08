"""Tests for break-the-glass emergency access."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from sense_loop.access.cedar.break_glass import (
    BreakTheGlassManager,
    BTGActivationResult,
    BTGRevocationResult,
    EmergencyType,
)


class TestEmergencyType:
    """Tests for EmergencyType enum."""

    def test_emergency_types_exist(self):
        """Test all emergency types are defined."""
        assert EmergencyType.MEDICAL_EMERGENCY == "medical_emergency"
        assert EmergencyType.SYSTEM_OUTAGE == "system_outage"
        assert EmergencyType.DISASTER_RECOVERY == "disaster_recovery"
        assert EmergencyType.CRITICAL_CARE == "critical_care"
        assert EmergencyType.LIFE_THREATENING == "life_threatening"
        assert EmergencyType.OTHER == "other"


class TestBTGActivationResult:
    """Tests for BTGActivationResult."""

    def test_to_dict(self):
        """Test converting result to dict."""
        btg_id = uuid4()
        expires = datetime.now() + timedelta(hours=4)

        result = BTGActivationResult(
            success=True,
            btg_access_id=btg_id,
            message="Access granted",
            expires_at=expires,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["btg_access_id"] == str(btg_id)
        assert d["message"] == "Access granted"
        assert d["expires_at"] == expires.isoformat()

    def test_to_dict_without_id(self):
        """Test converting failed result to dict."""
        result = BTGActivationResult(
            success=False,
            btg_access_id=None,
            message="Access denied",
            expires_at=None,
        )

        d = result.to_dict()

        assert d["success"] is False
        assert d["btg_access_id"] is None
        assert d["expires_at"] is None


class TestBreakTheGlassManager:
    """Tests for BreakTheGlassManager class."""

    def test_activate_success(self, mock_db_session, mock_practitioner, mock_organization):
        """Test successful BTG activation."""
        manager = BreakTheGlassManager(mock_db_session)

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Make the mock db.add set an id on the object (simulating SQLAlchemy behavior)
        def add_with_id(obj):
            if not hasattr(obj, 'id') or obj.id is None:
                obj.id = uuid4()

        mock_db_session.add.side_effect = add_with_id

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Medical emergency - patient in critical condition requiring immediate access",
            emergency_type=EmergencyType.MEDICAL_EMERGENCY,
        )

        assert result.success is True
        assert result.btg_access_id is not None
        assert result.expires_at is not None
        mock_db_session.add.assert_called_once()

    def test_activate_reason_too_short(self, mock_db_session, mock_practitioner, mock_organization):
        """Test BTG activation fails with short reason."""
        manager = BreakTheGlassManager(mock_db_session)

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Too short",  # Less than 20 characters
            emergency_type=EmergencyType.MEDICAL_EMERGENCY,
        )

        assert result.success is False
        assert "20 characters" in result.message

    def test_activate_no_org_role(self, mock_db_session, mock_practitioner, mock_organization):
        """Test BTG activation fails without org role."""
        manager = BreakTheGlassManager(mock_db_session)

        # Practitioner has no role in this org
        different_org_id = uuid4()

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=different_org_id,
            resource_type="patient",
            reason="Medical emergency requiring immediate access to patient records",
            emergency_type=EmergencyType.MEDICAL_EMERGENCY,
        )

        assert result.success is False
        assert "role" in result.message.lower()

    def test_activate_already_active(self, mock_db_session, mock_practitioner, mock_organization):
        """Test BTG activation fails when already active."""
        manager = BreakTheGlassManager(mock_db_session)

        # Mock existing active BTG
        existing_btg = MagicMock()
        existing_btg.id = uuid4()
        existing_btg.expires_at = datetime.now() + timedelta(hours=2)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing_btg
        mock_db_session.execute.return_value = mock_result

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Medical emergency requiring immediate access to patient records",
            emergency_type=EmergencyType.MEDICAL_EMERGENCY,
        )

        assert result.success is False
        assert "already exists" in result.message.lower()
        assert result.btg_access_id == existing_btg.id

    def test_activate_with_custom_duration(self, mock_db_session, mock_practitioner, mock_organization):
        """Test BTG activation with custom duration."""
        manager = BreakTheGlassManager(mock_db_session)

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Extended access needed for complex case requiring continuous monitoring",
            emergency_type=EmergencyType.CRITICAL_CARE,
            duration_hours=8,
        )

        assert result.success is True
        # Check that expires_at is approximately 8 hours from now
        expected_expiry = datetime.now() + timedelta(hours=8)
        assert abs((result.expires_at - expected_expiry).total_seconds()) < 5

    def test_activate_max_duration_cap(self, mock_db_session, mock_practitioner, mock_organization):
        """Test BTG duration is capped at maximum."""
        manager = BreakTheGlassManager(mock_db_session)

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Attempting to request excessively long access period for testing",
            emergency_type=EmergencyType.OTHER,
            duration_hours=100,  # Exceeds max
        )

        assert result.success is True
        # Should be capped at 24 hours
        max_expiry = datetime.now() + timedelta(hours=24)
        assert result.expires_at <= max_expiry + timedelta(seconds=5)

    def test_activate_string_emergency_type(self, mock_db_session, mock_practitioner, mock_organization):
        """Test BTG activation with string emergency type."""
        manager = BreakTheGlassManager(mock_db_session)

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Testing string emergency type conversion for BTG activation",
            emergency_type="medical_emergency",  # String instead of enum
        )

        assert result.success is True

    def test_revoke_success(self, mock_db_session, mock_practitioner):
        """Test successful BTG revocation."""
        manager = BreakTheGlassManager(mock_db_session)

        btg_access = MagicMock()
        btg_access.id = uuid4()
        btg_access.revoked_at = None
        btg_access.access_count = 5

        mock_db_session.get.return_value = btg_access

        result = manager.revoke(
            btg_access_id=btg_access.id,
            revoked_by=mock_practitioner,
            reason="Emergency resolved",
        )

        assert result.success is True
        assert result.access_count == 5
        assert btg_access.revoked_at is not None
        assert btg_access.revoked_by_id == mock_practitioner.id

    def test_revoke_not_found(self, mock_db_session, mock_practitioner):
        """Test revoking non-existent BTG."""
        manager = BreakTheGlassManager(mock_db_session)

        mock_db_session.get.return_value = None

        result = manager.revoke(
            btg_access_id=uuid4(),
            revoked_by=mock_practitioner,
        )

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_revoke_already_revoked(self, mock_db_session, mock_practitioner):
        """Test revoking already-revoked BTG."""
        manager = BreakTheGlassManager(mock_db_session)

        btg_access = MagicMock()
        btg_access.id = uuid4()
        btg_access.revoked_at = datetime.now()
        btg_access.access_count = 3

        mock_db_session.get.return_value = btg_access

        result = manager.revoke(
            btg_access_id=btg_access.id,
            revoked_by=mock_practitioner,
        )

        assert result.success is False
        assert "already revoked" in result.message.lower()

    def test_get_active_access(self, mock_db_session, mock_practitioner, mock_organization):
        """Test getting active BTG access."""
        manager = BreakTheGlassManager(mock_db_session)

        active_btg = MagicMock()
        active_btg.id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_btg]
        mock_db_session.execute.return_value = mock_result

        result = manager.get_active_access(
            practitioner_id=mock_practitioner.id,
            organization_id=mock_organization.id,
        )

        assert len(result) == 1
        assert result[0] == active_btg

    def test_notification_hook(self, mock_db_session, mock_practitioner, mock_organization):
        """Test that notification hooks are called."""
        manager = BreakTheGlassManager(mock_db_session)

        hook_called = []

        def test_hook(event, btg_access, practitioner):
            hook_called.append((event, btg_access, practitioner))

        manager.register_notification_hook(test_hook)

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Testing notification hooks for BTG activation events",
            emergency_type=EmergencyType.MEDICAL_EMERGENCY,
        )

        assert len(hook_called) == 1
        assert hook_called[0][0] == "btg_activated"

    def test_notification_hook_error_handled(self, mock_db_session, mock_practitioner, mock_organization):
        """Test that hook errors don't break activation."""
        manager = BreakTheGlassManager(mock_db_session)

        def failing_hook(event, btg_access, practitioner):
            raise Exception("Hook failed")

        manager.register_notification_hook(failing_hook)

        # Mock no existing active BTG
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Should not raise despite hook error
        result = manager.activate(
            practitioner=mock_practitioner,
            organization_id=mock_organization.id,
            resource_type="patient",
            reason="Testing error handling in notification hooks for BTG",
            emergency_type=EmergencyType.MEDICAL_EMERGENCY,
        )

        assert result.success is True

    def test_get_organization_btg_history(self, mock_db_session, mock_organization):
        """Test getting BTG history for organization."""
        manager = BreakTheGlassManager(mock_db_session)

        btg_records = [MagicMock(), MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = btg_records
        mock_db_session.execute.return_value = mock_result

        result = manager.get_organization_btg_history(
            organization_id=mock_organization.id,
            include_active=True,
            include_expired=True,
            include_revoked=True,
            limit=50,
        )

        assert len(result) == 3

    def test_cleanup_expired(self, mock_db_session):
        """Test cleanup of expired BTG records."""
        manager = BreakTheGlassManager(mock_db_session)

        expired_records = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = expired_records
        mock_db_session.execute.return_value = mock_result

        count = manager.cleanup_expired()

        assert count == 2
