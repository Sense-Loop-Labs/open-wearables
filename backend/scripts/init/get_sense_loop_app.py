#!/usr/bin/env python3
"""Get the Sense Loop application credentials.

Returns JSON with app_id for use in scripts.
The app_secret cannot be retrieved after creation.

Exit codes:
  0: Success (JSON printed to stdout)
  1: Application not found
"""

import json
import sys

from app.database import SessionLocal
from app.models import Application

APPLICATION_NAME = "Sense Loop Mobile"


def get_application() -> dict | None:
    """Get the application by name."""
    with SessionLocal() as db:
        app = db.query(Application).filter(Application.name == APPLICATION_NAME).first()
        if app:
            return {
                "app_id": app.app_id,
                "name": app.name,
            }
        return None


if __name__ == "__main__":
    app_data = get_application()
    if app_data:
        print(json.dumps(app_data))
        sys.exit(0)
    else:
        print(f"Application '{APPLICATION_NAME}' not found", file=sys.stderr)
        sys.exit(1)
