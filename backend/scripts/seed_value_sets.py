#!/usr/bin/env python3
"""Seed default value sets (surgery types, etc.)."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from sense_loop.services import ValueSetService


def seed_value_sets() -> None:
    """Seed all default value sets."""
    db = SessionLocal()
    try:
        service = ValueSetService(db)
        service.seed_defaults()
        print("Value sets seeded successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding value sets: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_value_sets()
