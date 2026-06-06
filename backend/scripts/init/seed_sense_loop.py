#!/usr/bin/env python3
"""Seed Sense Loop application and API key for Medplum integration.

This script creates:
1. "Sense Loop Mobile" application (for iOS app authentication)
2. API key (for Patient Creation Bot to create users)

Credentials are saved to:
- /tmp/sense-loop-credentials.json (for local retrieval)
- AWS SSM Parameter Store (for automated integration with Medplum)

Usage: python -m scripts.init.seed_sense_loop
"""

import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.database import SessionLocal
from app.models import ApiKey, Application, Developer
from app.services.api_key_service import api_key_service
from app.services.application_service import application_service

APPLICATION_NAME = "Sense Loop Mobile"
API_KEY_NAME = "Medplum Patient Creation Bot"
CREDENTIALS_FILE = Path("/tmp/sense-loop-credentials.json")

# SSM parameter paths - credentials stored here for Medplum integration
SSM_PARAM_PREFIX = "/sense-loop/{stage}/open-wearables"


def get_admin_developer(db) -> Developer | None:
    """Get the admin developer account."""
    return db.query(Developer).filter(Developer.email == settings.admin_email).first()


def get_application_by_name(db, name: str) -> Application | None:
    """Get application by name."""
    return db.query(Application).filter(Application.name == name).first()


def get_api_key_by_name(db, name: str) -> ApiKey | None:
    """Get API key by name."""
    return db.query(ApiKey).filter(ApiKey.name == name).first()


def save_credentials_to_ssm(credentials: dict, stage: str) -> bool:
    """Save credentials to AWS SSM Parameter Store.

    Parameters are stored as SecureString for encryption at rest.
    Returns True if successful, False otherwise.
    """
    if stage == "local":
        print("  Skipping SSM (local environment)")
        return False

    try:
        ssm = boto3.client("ssm", region_name="us-west-2")
        prefix = SSM_PARAM_PREFIX.format(stage=stage)

        # Map credential keys to SSM parameter names
        param_map = {
            "app_id": "app-id",
            "app_secret": "app-secret",
            "api_key": "api-key",
        }

        for key, param_name in param_map.items():
            if key in credentials:
                param_path = f"{prefix}/{param_name}"
                try:
                    ssm.put_parameter(
                        Name=param_path,
                        Value=credentials[key],
                        Type="SecureString",
                        Overwrite=True,
                        Description=f"Open Wearables {key} for Sense Loop integration",
                        Tags=[
                            {"Key": "Project", "Value": "SenseLoop"},
                            {"Key": "Stage", "Value": stage},
                            {"Key": "Component", "Value": "OpenWearables"},
                        ],
                    )
                    print(f"  ✓ Saved {param_path} to SSM")
                except ClientError as e:
                    # Tags can only be set on create, not update - retry without tags
                    if "TagResource" in str(e) or "ValidationException" in str(e):
                        ssm.put_parameter(
                            Name=param_path,
                            Value=credentials[key],
                            Type="SecureString",
                            Overwrite=True,
                            Description=f"Open Wearables {key} for Sense Loop integration",
                        )
                        print(f"  ✓ Updated {param_path} in SSM")
                    else:
                        raise

        return True
    except Exception as e:
        print(f"  Warning: Failed to save to SSM: {e}")
        print("  Credentials still available in /tmp/sense-loop-credentials.json")
        return False


def save_credentials(credentials: dict) -> None:
    """Save credentials to file and SSM for later retrieval."""
    # Load existing credentials if any
    existing = {}
    if CREDENTIALS_FILE.exists():
        try:
            existing = json.loads(CREDENTIALS_FILE.read_text())
        except Exception:
            pass

    # Merge new credentials
    existing.update(credentials)

    # Save to file (always, for backward compatibility)
    CREDENTIALS_FILE.write_text(json.dumps(existing, indent=2))
    os.chmod(CREDENTIALS_FILE, 0o600)  # Restrict permissions
    print(f"  Credentials saved to {CREDENTIALS_FILE}")

    # Save to SSM Parameter Store (for Medplum integration)
    # Use .value to get the string value from the enum (e.g., "staging" not "EnvironmentType.STAGING")
    stage = settings.environment.value if hasattr(settings.environment, 'value') else str(settings.environment)
    save_credentials_to_ssm(credentials, stage)


def seed_sense_loop() -> None:
    """Create Sense Loop application and API key if they don't exist."""
    credentials = {}

    with SessionLocal() as db:
        # Get admin developer
        admin = get_admin_developer(db)
        if not admin:
            print(f"Admin developer ({settings.admin_email}) not found.")
            print("Run seed_admin.py first: python -m scripts.init.seed_admin")
            return

        print(f"Using admin developer: {admin.email}")
        print()

        # Check if application already exists
        existing_app = get_application_by_name(db, APPLICATION_NAME)
        if existing_app:
            # Don't rotate - keep existing secret to avoid breaking Medplum integration
            print(f"Application '{APPLICATION_NAME}' already exists (app_id: {existing_app.app_id})")
            print("  Skipping secret rotation to preserve Medplum secrets sync")
            credentials["app_id"] = existing_app.app_id
            # Note: app_secret not included since we don't have the plaintext
        else:
            # Create application
            application, plain_secret = application_service.create_application(
                db, admin.id, APPLICATION_NAME
            )
            print(f"Created application '{APPLICATION_NAME}':")
            print(f"  App ID:     {application.app_id}")
            print(f"  App Secret: {plain_secret}")
            credentials["app_id"] = application.app_id
            credentials["app_secret"] = plain_secret

        print()

        # Check if API key already exists
        existing_key = get_api_key_by_name(db, API_KEY_NAME)

        if existing_key:
            print(f"API key '{API_KEY_NAME}' already exists:")
            print(f"  Key: {existing_key.id}")
            credentials["api_key"] = existing_key.id
        else:
            # Create API key
            api_key = api_key_service.create_api_key(db, admin.id, API_KEY_NAME)
            print(f"Created API key '{API_KEY_NAME}':")
            print(f"  Key: {api_key.id}")
            credentials["api_key"] = api_key.id

        # Save credentials to file
        if credentials:
            save_credentials(credentials)

        print()
        print("=" * 60)
        print("Sense Loop credentials configured!")
        print("=" * 60)


if __name__ == "__main__":
    seed_sense_loop()
