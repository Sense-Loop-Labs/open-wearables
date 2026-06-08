"""Tests for Cedar field filter."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from sense_loop.access.cedar.field_filter import FieldFilter


class TestFieldFilter:
    """Tests for FieldFilter class."""

    def test_filter_removes_hidden_fields(self, mock_db_session, mock_practitioner, mock_organization):
        """Test that hidden fields are removed from response."""
        filter_instance = FieldFilter(mock_db_session)

        # Mock _get_field_restrictions to return hidden fields
        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = ({"password_hash", "ssn"}, set())

            data = {
                "id": "123",
                "name": "John Doe",
                "password_hash": "secret",
                "ssn": "123-45-6789",
                "email": "john@example.com",
            }

            result = filter_instance.filter_fields(
                data, mock_practitioner, "patient", mock_organization.id
            )

            assert "id" in result
            assert "name" in result
            assert "email" in result
            assert "password_hash" not in result
            assert "ssn" not in result

    def test_filter_masks_hidden_fields_when_requested(self, mock_db_session, mock_practitioner, mock_organization):
        """Test that hidden fields are masked instead of removed."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = ({"password_hash"}, set())

            data = {"id": "123", "password_hash": "secret"}

            result = filter_instance.filter_fields(
                data, mock_practitioner, "patient", mock_organization.id, mask_hidden=True
            )

            assert result["password_hash"] == "***REDACTED***"

    def test_filter_list_of_dicts(self, mock_db_session, mock_practitioner, mock_organization):
        """Test filtering a list of dictionaries."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = ({"password_hash"}, set())

            data = [
                {"id": "1", "name": "John", "password_hash": "hash1"},
                {"id": "2", "name": "Jane", "password_hash": "hash2"},
            ]

            result = filter_instance.filter_fields(
                data, mock_practitioner, "patient", mock_organization.id
            )

            assert len(result) == 2
            assert "password_hash" not in result[0]
            assert "password_hash" not in result[1]
            assert result[0]["name"] == "John"
            assert result[1]["name"] == "Jane"

    def test_filter_nested_dict(self, mock_db_session, mock_practitioner, mock_organization):
        """Test filtering nested dictionaries."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = ({"secret", "nested.hidden"}, set())

            data = {
                "id": "123",
                "secret": "top_secret",
                "nested": {
                    "visible": "can see",
                    "hidden": "cannot see",
                },
            }

            result = filter_instance.filter_fields(
                data, mock_practitioner, "patient", mock_organization.id
            )

            assert "secret" not in result
            assert "nested" in result
            # Simple field names match at any level
            assert "hidden" not in result["nested"]
            assert result["nested"]["visible"] == "can see"

    def test_filter_empty_data(self, mock_db_session, mock_practitioner, mock_organization):
        """Test filtering empty data."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = ({"password_hash"}, set())

            assert filter_instance.filter_fields({}, mock_practitioner, "patient", mock_organization.id) == {}
            assert filter_instance.filter_fields([], mock_practitioner, "patient", mock_organization.id) == []

    def test_default_hidden_fields_for_patient(self, mock_db_session, mock_practitioner, mock_organization):
        """Test that default hidden fields are applied for patient type."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = (set(), set())  # No policy-based hidden fields

            data = {"id": "123", "name": "John", "password_hash": "secret"}

            result = filter_instance.filter_fields(
                data, mock_practitioner, "patient", mock_organization.id
            )

            # password_hash should be removed due to default hidden fields
            assert "password_hash" not in result

    def test_get_readonly_fields(self, mock_db_session, mock_practitioner, mock_organization):
        """Test getting readonly fields."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = (set(), {"mrn", "date_of_birth"})

            readonly = filter_instance.get_readonly_fields(
                mock_practitioner, "patient", mock_organization.id
            )

            assert "mrn" in readonly
            assert "date_of_birth" in readonly

    def test_validate_update_no_violations(self, mock_db_session, mock_practitioner, mock_organization):
        """Test validate_update with no readonly violations."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = (set(), {"mrn"})

            update_data = {"first_name": "John", "last_name": "Doe"}

            violations = filter_instance.validate_update(
                update_data, mock_practitioner, "patient", mock_organization.id
            )

            assert violations == []

    def test_validate_update_with_violations(self, mock_db_session, mock_practitioner, mock_organization):
        """Test validate_update with readonly violations."""
        filter_instance = FieldFilter(mock_db_session)

        with patch.object(filter_instance, "_get_field_restrictions") as mock_get:
            mock_get.return_value = (set(), {"mrn", "date_of_birth"})

            update_data = {"first_name": "John", "mrn": "NEW_MRN"}

            violations = filter_instance.validate_update(
                update_data, mock_practitioner, "patient", mock_organization.id
            )

            assert len(violations) == 1
            assert "mrn" in violations[0]
            assert "readonly" in violations[0].lower()

    def test_clear_cache(self, mock_db_session):
        """Test clearing the field restrictions cache."""
        filter_instance = FieldFilter(mock_db_session)

        # Populate cache
        filter_instance._cache["test_key"] = ({"field1"}, {"field2"})

        filter_instance.clear_cache()

        assert len(filter_instance._cache) == 0

    def test_cache_key_uniqueness(self, mock_db_session, mock_practitioner, mock_organization):
        """Test that cache keys are unique per practitioner/resource/org combination."""
        filter_instance = FieldFilter(mock_db_session)

        # First call should query (we'll check the cache is populated)
        with patch.object(filter_instance, "_get_applicable_policies") as mock_policies:
            mock_policies.return_value = []

            filter_instance._get_field_restrictions(
                mock_practitioner, "patient", mock_organization.id
            )

            cache_key = f"{mock_practitioner.id}:patient:{mock_organization.id}"
            assert cache_key in filter_instance._cache

        # Second call should use cache
        with patch.object(filter_instance, "_get_applicable_policies") as mock_policies:
            filter_instance._get_field_restrictions(
                mock_practitioner, "patient", mock_organization.id
            )
            # Should not call _get_applicable_policies again due to cache
            mock_policies.assert_not_called()
