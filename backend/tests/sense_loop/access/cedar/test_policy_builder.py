"""Tests for Cedar policy builder."""

import pytest

from sense_loop.access.cedar.policy_builder import (
    build_cedar_policy,
    build_cedar_schema,
    build_policies_from_db,
    get_hidden_fields_from_policy,
    get_readonly_fields_from_policy,
)


class TestBuildCedarPolicy:
    """Tests for build_cedar_policy function."""

    def test_basic_permit_policy(self, mock_access_policy):
        """Test building a basic permit policy."""
        policy_str = build_cedar_policy(mock_access_policy)

        assert "permit" in policy_str.lower()
        assert mock_access_policy.code in policy_str
        assert "Patient" in policy_str  # Resource type capitalized

    def test_forbid_policy(self, mock_access_policy):
        """Test building a forbid policy."""
        mock_access_policy.effect = "forbid"

        policy_str = build_cedar_policy(mock_access_policy)

        assert "forbid" in policy_str.lower()

    def test_policy_with_actions(self, mock_access_policy):
        """Test policy includes action constraints."""
        policy_str = build_cedar_policy(mock_access_policy)

        # Should include action list
        assert "action in [" in policy_str or "action" in policy_str
        assert 'Action::"read"' in policy_str

    def test_policy_with_same_organization_condition(self, mock_access_policy):
        """Test policy includes organization condition."""
        policy_str = build_cedar_policy(mock_access_policy)

        assert "principal.organization_id == resource.organization_id" in policy_str

    def test_policy_with_enrollment_status_condition(self, mock_access_policy):
        """Test policy with enrollment status condition."""
        mock_access_policy.rules["conditions"]["enrollment_status"] = ["active", "enrolled"]

        policy_str = build_cedar_policy(mock_access_policy)

        assert "enrollment_status" in policy_str
        assert "active" in policy_str

    def test_policy_with_resource_active_condition(self, mock_access_policy):
        """Test policy with resource active condition."""
        mock_access_policy.rules["conditions"]["resource_active"] = True

        policy_str = build_cedar_policy(mock_access_policy)

        assert "is_active" in policy_str

    def test_policy_priority_comment(self, mock_access_policy):
        """Test that policy includes priority in comments."""
        policy_str = build_cedar_policy(mock_access_policy)

        assert f"Priority: {mock_access_policy.priority}" in policy_str

    def test_policy_without_conditions(self, mock_access_policy):
        """Test policy without conditions."""
        mock_access_policy.rules["conditions"] = {}

        policy_str = build_cedar_policy(mock_access_policy)

        # Should not have when clause
        assert "when {" not in policy_str or policy_str.count("{") <= 1

    def test_policy_with_custom_resource_attrs(self, mock_access_policy):
        """Test policy with custom resource attribute conditions."""
        mock_access_policy.rules["conditions"]["resource_attrs"] = {
            "severity": "critical",
            "count": 5,
            "is_urgent": True,
        }

        policy_str = build_cedar_policy(mock_access_policy)

        assert "severity" in policy_str
        assert "critical" in policy_str


class TestBuildPoliciesFromDb:
    """Tests for build_policies_from_db function."""

    def test_combines_multiple_policies(self, mock_access_policy):
        """Test combining multiple policies."""
        policy1 = mock_access_policy
        policy2 = type(mock_access_policy)()
        policy2.code = "alert_read"
        policy2.name = "Alert Read"
        policy2.rules = {
            "resource_type": "alert",
            "actions": ["read"],
            "conditions": {},
        }
        policy2.effect = "permit"
        policy2.priority = 50
        policy2.is_active = True

        combined = build_policies_from_db([policy1, policy2])

        assert policy1.code in combined
        assert "alert_read" in combined

    def test_sorts_by_priority(self, mock_access_policy):
        """Test that policies are sorted by priority (highest first)."""
        policy1 = mock_access_policy
        policy1.priority = 50

        policy2 = type(mock_access_policy)()
        policy2.code = "high_priority"
        policy2.rules = {"resource_type": "patient", "actions": ["read"], "conditions": {}}
        policy2.effect = "permit"
        policy2.priority = 100
        policy2.is_active = True

        combined = build_policies_from_db([policy1, policy2])

        # High priority policy should appear first
        high_priority_pos = combined.find("high_priority")
        low_priority_pos = combined.find(policy1.code)
        assert high_priority_pos < low_priority_pos

    def test_excludes_inactive_policies(self, mock_access_policy):
        """Test that inactive policies are excluded."""
        mock_access_policy.is_active = False

        combined = build_policies_from_db([mock_access_policy])

        assert mock_access_policy.code not in combined or combined == ""


class TestGetFieldsFromPolicy:
    """Tests for field extraction functions."""

    def test_get_hidden_fields(self, mock_access_policy):
        """Test extracting hidden fields from policy."""
        hidden = get_hidden_fields_from_policy(mock_access_policy)

        assert "password_hash" in hidden

    def test_get_hidden_fields_empty(self, mock_access_policy):
        """Test getting hidden fields when none defined."""
        mock_access_policy.rules["hidden_fields"] = []

        hidden = get_hidden_fields_from_policy(mock_access_policy)

        assert hidden == []

    def test_get_readonly_fields(self, mock_access_policy):
        """Test extracting readonly fields from policy."""
        readonly = get_readonly_fields_from_policy(mock_access_policy)

        assert "mrn" in readonly

    def test_get_readonly_fields_empty(self, mock_access_policy):
        """Test getting readonly fields when none defined."""
        mock_access_policy.rules["readonly_fields"] = []

        readonly = get_readonly_fields_from_policy(mock_access_policy)

        assert readonly == []

    def test_get_fields_missing_key(self, mock_access_policy):
        """Test getting fields when key is missing from rules."""
        del mock_access_policy.rules["hidden_fields"]
        del mock_access_policy.rules["readonly_fields"]

        hidden = get_hidden_fields_from_policy(mock_access_policy)
        readonly = get_readonly_fields_from_policy(mock_access_policy)

        assert hidden == []
        assert readonly == []


class TestBuildCedarSchema:
    """Tests for Cedar schema generation."""

    def test_schema_includes_entities(self):
        """Test that schema includes all entity types."""
        schema = build_cedar_schema()

        assert "entity Organization" in schema
        assert "entity Practitioner" in schema
        assert "entity Patient" in schema
        assert "entity Alert" in schema
        assert "entity CarePlan" in schema

    def test_schema_includes_actions(self):
        """Test that schema includes action definitions."""
        schema = build_cedar_schema()

        assert "action read" in schema
        assert "action create" in schema
        assert "action update" in schema
        assert "action delete" in schema
        assert "action acknowledge" in schema
        assert "action resolve" in schema

    def test_schema_includes_namespace(self):
        """Test that schema uses SenseLoop namespace."""
        schema = build_cedar_schema()

        assert "namespace SenseLoop" in schema

    def test_schema_includes_practitioner_attributes(self):
        """Test that practitioner entity has permission attributes."""
        schema = build_cedar_schema()

        assert "can_manage_patients" in schema
        assert "can_manage_alerts" in schema
        assert "can_resolve_alerts" in schema
