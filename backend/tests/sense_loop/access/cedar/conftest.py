"""Fixtures for Cedar authorization tests."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_organization():
    """Create a mock organization."""
    org = MagicMock()
    org.id = uuid4()
    org.name = "Test Organization"
    org.slug = "test-org"
    org.is_active = True
    return org


@pytest.fixture
def mock_role_definition():
    """Create a mock role definition."""
    role_def = MagicMock()
    role_def.id = uuid4()
    role_def.code = "doctor"
    role_def.display_name = "Physician"
    role_def.can_manage_patients = True
    role_def.can_manage_alerts = True
    role_def.can_resolve_alerts = True
    role_def.can_acknowledge_alerts = True
    role_def.can_manage_care_plans = True
    role_def.can_manage_clinicians = False
    role_def.can_manage_org_settings = False
    role_def.can_view_audit_logs = False
    role_def.can_manage_alert_protocols = False
    role_def.can_export_data = True
    role_def.is_system_role = True
    role_def.is_active = True
    return role_def


@pytest.fixture
def mock_practitioner_role(mock_organization, mock_role_definition):
    """Create a mock practitioner role."""
    role = MagicMock()
    role.id = uuid4()
    role.organization_id = mock_organization.id
    role.role_definition_id = mock_role_definition.id
    role.role_definition = mock_role_definition
    role.organization = mock_organization
    role.is_active = True
    role.is_primary = True
    return role


@pytest.fixture
def mock_practitioner(mock_practitioner_role):
    """Create a mock practitioner with roles."""
    practitioner = MagicMock()
    practitioner.id = uuid4()
    practitioner.email = "doctor@test.com"
    practitioner.first_name = "Test"
    practitioner.last_name = "Doctor"
    practitioner.is_active = True
    practitioner.practitioner_roles = [mock_practitioner_role]
    return practitioner


@pytest.fixture
def mock_patient(mock_organization):
    """Create a mock patient."""
    patient = MagicMock()
    patient.id = uuid4()
    patient.organization_id = mock_organization.id
    patient.first_name = "John"
    patient.last_name = "Doe"
    patient.mrn = "MRN123"
    patient.enrollment_status = "active"
    patient.is_active = True
    patient.password_hash = "hashed_password"
    return patient


@pytest.fixture
def sample_access_policy():
    """Create a sample access policy dict."""
    return {
        "id": uuid4(),
        "code": "patient_full_access",
        "name": "Patient Full Access",
        "description": "Full access to patient records",
        "organization_id": None,
        "rules": {
            "resource_type": "patient",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": ["password_hash"],
            "readonly_fields": ["mrn"],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_active": True,
        "is_system_policy": True,
    }


@pytest.fixture
def mock_access_policy(sample_access_policy):
    """Create a mock AccessPolicy object."""
    policy = MagicMock()
    policy.id = sample_access_policy["id"]
    policy.code = sample_access_policy["code"]
    policy.name = sample_access_policy["name"]
    policy.description = sample_access_policy["description"]
    policy.organization_id = sample_access_policy["organization_id"]
    policy.rules = sample_access_policy["rules"]
    policy.effect = sample_access_policy["effect"]
    policy.priority = sample_access_policy["priority"]
    policy.is_active = sample_access_policy["is_active"]
    policy.is_system_policy = sample_access_policy["is_system_policy"]
    return policy


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.get = MagicMock(return_value=None)
    return session


@pytest.fixture
def sample_patient_data():
    """Sample patient data dict for filtering tests."""
    return {
        "id": str(uuid4()),
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "555-1234",
        "mrn": "MRN123",
        "password_hash": "secret_hash",
        "enrollment_status": "active",
        "is_active": True,
        "date_of_birth": "1990-01-15",
        "organization_id": str(uuid4()),
    }


@pytest.fixture
def sample_patient_list(sample_patient_data):
    """Sample list of patient data for filtering tests."""
    return [
        sample_patient_data,
        {
            **sample_patient_data,
            "id": str(uuid4()),
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@example.com",
            "mrn": "MRN456",
        },
    ]
