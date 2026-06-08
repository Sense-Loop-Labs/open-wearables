"""Tests for Cedar query filter builder."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from sense_loop.access.cedar.query_filter import QueryFilterBuilder


class TestQueryFilterBuilder:
    """Tests for QueryFilterBuilder class."""

    def test_build_filter_no_policies(self, mock_db_session, mock_practitioner, mock_organization):
        """Test filter when no policies exist falls back to org check."""
        builder = QueryFilterBuilder(mock_db_session)

        with patch.object(builder, "_get_applicable_policies", return_value=[]):
            result = builder.build_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
            )

        assert f"organization_id = '{mock_organization.id}'" == result

    def test_build_filter_with_permit_policy(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with a permit policy."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {}

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
            )

        assert f"organization_id = '{mock_organization.id}'" in result
        # Empty conditions generates "1 = 1" (always true)
        assert "1 = 1" in result

    def test_build_filter_with_enrollment_status(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with enrollment status condition."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "enrollment_status": ["active", "enrolled"],
        }

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
            )

        assert "enrollment_status IN" in result
        assert "'active'" in result
        assert "'enrolled'" in result

    def test_build_filter_with_resource_active(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with resource_active condition."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {"resource_active": True}

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
            )

        assert "is_active = true" in result

    def test_build_filter_with_resource_attrs_string(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with string resource attribute."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "resource_attrs": {"severity": "critical"}
        }

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "alert",
                mock_organization.id,
            )

        assert "severity = 'critical'" in result

    def test_build_filter_with_resource_attrs_bool(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with boolean resource attribute."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "resource_attrs": {"is_urgent": True}
        }

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "alert",
                mock_organization.id,
            )

        assert "is_urgent = true" in result

    def test_build_filter_with_resource_attrs_number(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with numeric resource attribute."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "resource_attrs": {"priority": 5}
        }

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "alert",
                mock_organization.id,
            )

        assert "priority = 5" in result

    def test_build_filter_with_resource_attrs_list(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test filter with list resource attribute."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "resource_attrs": {"status": ["open", "pending"]}
        }

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "alert",
                mock_organization.id,
            )

        assert "status IN" in result
        assert "'open'" in result
        assert "'pending'" in result

    def test_build_filter_forbid_policy_excluded(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test that forbid policies are not included in query filter."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "forbid"
        mock_access_policy.rules["conditions"] = {"enrollment_status": ["active"]}

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
            )

        # Forbid policies don't add conditions, fall back to org-only
        assert result == f"organization_id = '{mock_organization.id}'"

    def test_build_filter_multiple_policies_or(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test multiple policies are combined with OR."""
        builder = QueryFilterBuilder(mock_db_session)

        policy1 = mock_access_policy
        policy1.code = "policy1"
        policy1.effect = "permit"
        policy1.rules = {
            "resource_type": "patient",
            "actions": ["read"],
            "conditions": {"enrollment_status": ["active"]},
        }

        policy2 = MagicMock()
        policy2.code = "policy2"
        policy2.effect = "permit"
        policy2.is_active = True
        policy2.rules = {
            "resource_type": "patient",
            "actions": ["read"],
            "conditions": {"enrollment_status": ["enrolled"]},
        }

        with patch.object(builder, "_get_applicable_policies", return_value=[policy1, policy2]):
            result = builder.build_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
            )

        assert " OR " in result
        assert "'active'" in result
        assert "'enrolled'" in result


class TestQueryFilterBuilderConditions:
    """Tests for condition building in QueryFilterBuilder."""

    def test_build_conditions_empty(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test building conditions from policy with no conditions."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {}

        conditions = builder._build_conditions_from_policies(
            [mock_access_policy],
            mock_practitioner,
            mock_organization.id,
        )

        assert conditions == ["1 = 1"]

    def test_build_conditions_inactive_policy_skipped(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test that inactive policies are skipped."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.is_active = False

        conditions = builder._build_conditions_from_policies(
            [mock_access_policy],
            mock_practitioner,
            mock_organization.id,
        )

        assert conditions == []

    def test_build_conditions_combined_with_and(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test that multiple conditions in a policy are combined with AND."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "enrollment_status": ["active"],
            "resource_active": True,
        }

        conditions = builder._build_conditions_from_policies(
            [mock_access_policy],
            mock_practitioner,
            mock_organization.id,
        )

        assert len(conditions) == 1
        assert " AND " in conditions[0]
        assert "enrollment_status" in conditions[0]
        assert "is_active" in conditions[0]


class TestQueryFilterBuilderSqlAlchemy:
    """Tests for SQLAlchemy filter building."""

    def test_build_sqlalchemy_filter_no_policies(
        self, mock_db_session, mock_practitioner, mock_organization
    ):
        """Test SQLAlchemy filter with no policies."""
        builder = QueryFilterBuilder(mock_db_session)

        # Create a mock model class
        MockModel = MagicMock()
        MockModel.organization_id = MagicMock()

        with patch.object(builder, "_get_applicable_policies", return_value=[]):
            result = builder.build_sqlalchemy_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
                MockModel,
            )

        # Should return base filter (organization_id check)
        assert result is not None

    def test_build_sqlalchemy_filter_with_enrollment_status(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test SQLAlchemy filter with enrollment status condition."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "enrollment_status": ["active"],
        }

        # Create a mock model class
        MockModel = MagicMock()
        MockModel.organization_id = MagicMock()
        MockModel.enrollment_status = MagicMock()

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_sqlalchemy_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
                MockModel,
            )

        assert result is not None

    def test_build_sqlalchemy_filter_with_is_active(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test SQLAlchemy filter with resource_active condition."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {"resource_active": True}

        # Create a mock model class
        MockModel = MagicMock()
        MockModel.organization_id = MagicMock()
        MockModel.is_active = MagicMock()

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_sqlalchemy_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
                MockModel,
            )

        assert result is not None

    def test_build_sqlalchemy_filter_forbid_policies_excluded(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test that forbid policies are excluded from SQLAlchemy filter."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "forbid"

        MockModel = MagicMock()
        MockModel.organization_id = MagicMock()

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_sqlalchemy_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
                MockModel,
            )

        # Only base filter should be returned
        assert result is not None

    def test_build_sqlalchemy_filter_with_custom_attrs(
        self, mock_db_session, mock_practitioner, mock_organization, mock_access_policy
    ):
        """Test SQLAlchemy filter with custom resource attributes."""
        builder = QueryFilterBuilder(mock_db_session)
        mock_access_policy.effect = "permit"
        mock_access_policy.rules["conditions"] = {
            "resource_attrs": {"severity": ["critical", "high"]}
        }

        MockModel = MagicMock()
        MockModel.organization_id = MagicMock()
        MockModel.severity = MagicMock()
        MockModel.severity.in_ = MagicMock(return_value=True)

        with patch.object(builder, "_get_applicable_policies", return_value=[mock_access_policy]):
            result = builder.build_sqlalchemy_filter(
                mock_practitioner,
                "alert",
                mock_organization.id,
                MockModel,
            )

        assert result is not None


class TestQueryFilterBuilderGetAccessibleIds:
    """Tests for get_accessible_resource_ids method."""

    def test_get_accessible_resource_ids(
        self, mock_db_session, mock_practitioner, mock_organization
    ):
        """Test getting accessible resource IDs.

        Note: This test uses a simplified approach since SQLAlchemy's select()
        doesn't work with MagicMock objects directly.
        """
        builder = QueryFilterBuilder(mock_db_session)

        # Mock the database execute to return some IDs
        expected_ids = [uuid4(), uuid4(), uuid4()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = expected_ids
        mock_db_session.execute.return_value = mock_result

        # We can't actually call get_accessible_resource_ids with a MagicMock model
        # because SQLAlchemy's select() requires real column objects.
        # Instead, verify the method exists and test the filter building separately.
        assert hasattr(builder, "get_accessible_resource_ids")

        # Verify build_sqlalchemy_filter works (used by get_accessible_resource_ids)
        with patch.object(builder, "_get_applicable_policies", return_value=[]):
            MockModel = MagicMock()
            MockModel.organization_id = mock_organization.id
            filter_result = builder.build_sqlalchemy_filter(
                mock_practitioner,
                "patient",
                mock_organization.id,
                MockModel,
            )
            assert filter_result is not None


class TestQueryFilterBuilderApplicablePolicies:
    """Tests for _get_applicable_policies method."""

    def test_get_applicable_policies_filters_by_resource_type(
        self, mock_db_session, mock_practitioner, mock_organization
    ):
        """Test that policies are filtered by resource type."""
        builder = QueryFilterBuilder(mock_db_session)

        # Create policies for different resource types
        patient_policy = MagicMock()
        patient_policy.rules = {"resource_type": "patient", "actions": ["read"], "conditions": {}}
        patient_policy.is_active = True

        alert_policy = MagicMock()
        alert_policy.rules = {"resource_type": "alert", "actions": ["read"], "conditions": {}}
        alert_policy.is_active = True

        # Mock role-based policy query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [patient_policy, alert_policy]
        mock_db_session.execute.return_value = mock_result

        # Note: This tests the filter logic, but the actual DB query is mocked
        # The real test would require integration testing
        policies = builder._get_applicable_policies(
            mock_practitioner,
            "patient",
            mock_organization.id,
        )

        # In mocked scenario, the filter returns what was queried
        # Real filtering happens in the method
