"""Tests for Cedar entity builder."""

from uuid import uuid4

import pytest

from sense_loop.access.cedar.entity_builder import (
    CedarEntity,
    build_entities_for_authorization,
    build_patient_entity,
    build_practitioner_entity,
    build_resource_entity,
    make_entity_uid,
)


class TestMakeEntityUid:
    """Tests for make_entity_uid function."""

    def test_basic_uid(self):
        """Test creating a basic entity UID."""
        uid = make_entity_uid("Patient", "123")

        assert uid == 'Patient::"123"'

    def test_uid_with_uuid(self):
        """Test creating UID with UUID."""
        entity_id = uuid4()

        uid = make_entity_uid("Practitioner", entity_id)

        assert uid == f'Practitioner::"{entity_id}"'

    def test_different_entity_types(self):
        """Test UID generation for different entity types."""
        assert make_entity_uid("Organization", "org1") == 'Organization::"org1"'
        assert make_entity_uid("Alert", "alert1") == 'Alert::"alert1"'
        assert make_entity_uid("Role", "doctor") == 'Role::"doctor"'


class TestCedarEntity:
    """Tests for CedarEntity dataclass."""

    def test_to_dict_basic(self):
        """Test converting entity to dict format."""
        entity = CedarEntity(
            uid='Patient::"123"',
            attrs={"name": "John", "is_active": True},
            parents=[],
        )

        result = entity.to_dict()

        assert result["uid"] == 'Patient::"123"'
        assert result["attrs"]["name"] == "John"
        assert result["attrs"]["is_active"] is True
        assert result["parents"] == []

    def test_to_dict_with_parents(self):
        """Test converting entity with parents to dict."""
        entity = CedarEntity(
            uid='Patient::"123"',
            attrs={},
            parents=['Organization::"org1"', 'Role::"doctor"'],
        )

        result = entity.to_dict()

        assert len(result["parents"]) == 2
        assert {"__expr": 'Organization::"org1"'} in result["parents"]


class TestBuildPractitionerEntity:
    """Tests for build_practitioner_entity function."""

    def test_basic_practitioner_entity(self, mock_practitioner, mock_organization):
        """Test building a basic practitioner entity."""
        entity = build_practitioner_entity(mock_practitioner, mock_organization.id)

        assert f'Practitioner::"{mock_practitioner.id}"' == entity.uid
        assert entity.attrs["email"] == mock_practitioner.email
        assert entity.attrs["is_active"] is True
        assert str(mock_organization.id) in entity.attrs["organization_id"]

    def test_practitioner_with_role(self, mock_practitioner, mock_organization, mock_role_definition):
        """Test practitioner entity includes role information."""
        entity = build_practitioner_entity(mock_practitioner, mock_organization.id)

        # Should have role as parent
        assert any("Role" in p for p in entity.parents)
        assert entity.attrs["role_code"] == mock_role_definition.code

    def test_practitioner_permission_attrs(self, mock_practitioner, mock_organization, mock_role_definition):
        """Test practitioner entity includes permission attributes."""
        entity = build_practitioner_entity(mock_practitioner, mock_organization.id)

        assert entity.attrs["can_manage_patients"] == mock_role_definition.can_manage_patients
        assert entity.attrs["can_manage_alerts"] == mock_role_definition.can_manage_alerts
        assert entity.attrs["can_resolve_alerts"] == mock_role_definition.can_resolve_alerts

    def test_practitioner_with_explicit_role_codes(self, mock_practitioner, mock_organization):
        """Test practitioner entity with explicit role codes."""
        entity = build_practitioner_entity(
            mock_practitioner, mock_organization.id, role_codes=["admin", "doctor"]
        )

        assert 'Role::"admin"' in entity.parents
        assert 'Role::"doctor"' in entity.parents


class TestBuildPatientEntity:
    """Tests for build_patient_entity function."""

    def test_basic_patient_entity(self, mock_patient):
        """Test building a basic patient entity."""
        entity = build_patient_entity(mock_patient)

        assert f'Patient::"{mock_patient.id}"' == entity.uid
        assert entity.attrs["organization_id"] == str(mock_patient.organization_id)
        assert entity.attrs["enrollment_status"] == "active"
        assert entity.attrs["is_active"] is True

    def test_patient_has_organization_parent(self, mock_patient):
        """Test patient entity has organization as parent."""
        entity = build_patient_entity(mock_patient)

        assert any("Organization" in p for p in entity.parents)

    def test_patient_with_mrn(self, mock_patient):
        """Test patient entity with MRN."""
        entity = build_patient_entity(mock_patient)

        assert entity.attrs["has_mrn"] is True

    def test_patient_without_mrn(self, mock_patient):
        """Test patient entity without MRN."""
        mock_patient.mrn = None

        entity = build_patient_entity(mock_patient)

        assert entity.attrs["has_mrn"] is False

    def test_patient_with_monitoring_dates(self, mock_patient):
        """Test patient entity with monitoring dates."""
        from datetime import date

        mock_patient.monitoring_start_date = date(2024, 1, 1)
        mock_patient.monitoring_end_date = date(2024, 12, 31)

        entity = build_patient_entity(mock_patient)

        assert "monitoring_start_date" in entity.attrs
        assert "monitoring_end_date" in entity.attrs


class TestBuildResourceEntity:
    """Tests for build_resource_entity function."""

    def test_basic_resource_entity(self):
        """Test building a basic resource entity."""
        resource_id = uuid4()
        org_id = uuid4()

        entity = build_resource_entity("alert", resource_id, org_id)

        assert f'Alert::"{resource_id}"' == entity.uid
        assert entity.attrs["organization_id"] == str(org_id)

    def test_resource_without_id(self):
        """Test building resource entity without specific ID."""
        org_id = uuid4()

        entity = build_resource_entity("patient", None, org_id)

        assert "__type_check__" in entity.uid

    def test_resource_with_extra_attrs(self):
        """Test building resource entity with extra attributes."""
        resource_id = uuid4()
        org_id = uuid4()
        extra = {"severity": "critical", "status": "open"}

        entity = build_resource_entity("alert", resource_id, org_id, extra)

        assert entity.attrs["severity"] == "critical"
        assert entity.attrs["status"] == "open"

    def test_resource_type_capitalization(self):
        """Test that resource type is capitalized correctly."""
        org_id = uuid4()

        entity = build_resource_entity("care_plan", uuid4(), org_id)

        assert "Care_Plan" in entity.uid or "CarePlan" in entity.uid


class TestBuildEntitiesForAuthorization:
    """Tests for build_entities_for_authorization function."""

    def test_returns_list_of_entities(self, mock_practitioner, mock_organization):
        """Test that function returns list of entity dicts."""
        entities = build_entities_for_authorization(
            mock_practitioner,
            "patient",
            uuid4(),
            mock_organization.id,
        )

        assert isinstance(entities, list)
        assert len(entities) >= 2  # At least practitioner and resource

    def test_includes_practitioner_entity(self, mock_practitioner, mock_organization):
        """Test that practitioner entity is included."""
        entities = build_entities_for_authorization(
            mock_practitioner,
            "patient",
            uuid4(),
            mock_organization.id,
        )

        uids = [e["uid"] for e in entities]
        assert any("Practitioner" in uid for uid in uids)

    def test_includes_resource_entity(self, mock_practitioner, mock_organization):
        """Test that resource entity is included."""
        resource_id = uuid4()

        entities = build_entities_for_authorization(
            mock_practitioner,
            "patient",
            resource_id,
            mock_organization.id,
        )

        uids = [e["uid"] for e in entities]
        assert any("Patient" in uid for uid in uids)

    def test_includes_organization_entity(self, mock_practitioner, mock_organization):
        """Test that organization entity is included."""
        entities = build_entities_for_authorization(
            mock_practitioner,
            "patient",
            uuid4(),
            mock_organization.id,
        )

        uids = [e["uid"] for e in entities]
        assert any("Organization" in uid for uid in uids)

    def test_with_resource_attrs(self, mock_practitioner, mock_organization):
        """Test including extra resource attributes."""
        entities = build_entities_for_authorization(
            mock_practitioner,
            "alert",
            uuid4(),
            mock_organization.id,
            resource_attrs={"severity": "high"},
        )

        # Find the alert entity
        alert_entity = next(e for e in entities if "Alert" in e["uid"])
        assert alert_entity["attrs"]["severity"] == "high"
