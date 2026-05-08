#!/usr/bin/env python3
"""Get the Sense Loop API key for Medplum integration.

Returns just the API key value for use in scripts.
Exit codes:
  0: Success (key printed to stdout)
  1: Key not found
"""

import sys

from app.database import SessionLocal
from app.models import ApiKey

API_KEY_NAME = "Medplum Patient Creation Bot"


def get_api_key() -> str | None:
    """Get the API key by name."""
    with SessionLocal() as db:
        api_key = db.query(ApiKey).filter(ApiKey.name == API_KEY_NAME).first()
        return api_key.id if api_key else None


if __name__ == "__main__":
    key = get_api_key()
    if key:
        print(key)
        sys.exit(0)
    else:
        print(f"API key '{API_KEY_NAME}' not found", file=sys.stderr)
        sys.exit(1)
