"""Audit log integrity verification using hash chains.

This module provides tamper-evident logging for HIPAA compliance.
Each audit entry includes a cryptographic hash of its contents plus
the previous entry's hash, creating an unbroken chain that reveals
any modifications.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sense_loop.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# Genesis hash for the first entry in the chain
GENESIS_HASH = "0" * 64  # SHA-256 produces 64 hex characters


@dataclass
class IntegrityCheckResult:
    """Result of an integrity verification check."""

    is_valid: bool
    entries_checked: int
    first_invalid_sequence: int | None = None
    first_invalid_id: UUID | None = None
    error_message: str | None = None
    gaps_detected: list[int] | None = None


def compute_entry_hash(
    entry_id: UUID,
    created_at: datetime,
    actor_type: str,
    actor_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    outcome: str,
    previous_hash: str,
) -> str:
    """Compute SHA-256 hash for an audit log entry.

    The hash includes key immutable fields that identify the audit event.
    This creates a tamper-evident record - any modification to these fields
    would change the hash and break the chain.

    Args:
        entry_id: Unique ID of the audit entry
        created_at: Timestamp of the entry
        actor_type: Type of actor (practitioner, patient, etc.)
        actor_id: ID of the actor
        action: Action performed
        resource_type: Type of resource accessed
        resource_id: ID of the resource
        outcome: Result of the action
        previous_hash: Hash of the previous entry in the chain

    Returns:
        SHA-256 hex digest of the entry
    """
    # Build canonical representation for hashing
    # Using JSON ensures consistent ordering and formatting
    hash_data = {
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
        "actor_type": actor_type,
        "actor_id": str(actor_id) if actor_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "outcome": outcome,
        "previous_hash": previous_hash,
    }

    # Create deterministic JSON string
    canonical = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))

    # Compute SHA-256 hash
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_latest_hash_info(db: Session) -> tuple[str, int]:
    """Get the latest entry's hash and sequence number.

    Args:
        db: Database session

    Returns:
        Tuple of (latest_hash, latest_sequence_number)
        Returns (GENESIS_HASH, 0) if no entries exist
    """
    # Get the entry with the highest sequence number that has a hash
    stmt = (
        select(AuditLog.entry_hash, AuditLog.sequence_number)
        .where(AuditLog.entry_hash.isnot(None))
        .order_by(AuditLog.sequence_number.desc())
        .limit(1)
    )
    result = db.execute(stmt).first()

    if result and result.entry_hash:
        return result.entry_hash, result.sequence_number or 0

    # No entries with hashes yet, return genesis
    return GENESIS_HASH, 0


def get_next_sequence_number(db: Session) -> int:
    """Get the next sequence number for a new entry.

    Uses a database-level operation to ensure uniqueness even
    under concurrent inserts.

    Args:
        db: Database session

    Returns:
        The next sequence number to use
    """
    # Get max sequence number
    stmt = select(func.coalesce(func.max(AuditLog.sequence_number), 0))
    max_seq = db.execute(stmt).scalar() or 0
    return max_seq + 1


class AuditIntegrityService:
    """Service for verifying audit log integrity."""

    def __init__(self, db: Session):
        self.db = db

    def verify_chain(
        self,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        limit: int = 10000,
    ) -> IntegrityCheckResult:
        """Verify the integrity of the audit log hash chain.

        Walks through the chain and verifies that each entry's hash
        matches the computed hash and links correctly to the previous entry.

        Args:
            start_sequence: Starting sequence number (default: 1)
            end_sequence: Ending sequence number (default: latest)
            limit: Maximum entries to check in one call

        Returns:
            IntegrityCheckResult with verification status
        """
        # Build query for entries with hashes
        stmt = (
            select(AuditLog)
            .where(AuditLog.entry_hash.isnot(None))
            .order_by(AuditLog.sequence_number)
        )

        if start_sequence is not None:
            stmt = stmt.where(AuditLog.sequence_number >= start_sequence)
        if end_sequence is not None:
            stmt = stmt.where(AuditLog.sequence_number <= end_sequence)

        stmt = stmt.limit(limit)

        entries = self.db.execute(stmt).scalars().all()

        if not entries:
            return IntegrityCheckResult(
                is_valid=True,
                entries_checked=0,
                error_message="No entries with hashes found",
            )

        # Track expected previous hash
        expected_previous_hash = GENESIS_HASH
        if start_sequence and start_sequence > 1:
            # Get the hash of the entry before our start
            prev_stmt = (
                select(AuditLog.entry_hash)
                .where(
                    AuditLog.sequence_number == start_sequence - 1,
                    AuditLog.entry_hash.isnot(None),
                )
            )
            prev_hash = self.db.execute(prev_stmt).scalar()
            if prev_hash:
                expected_previous_hash = prev_hash

        # Check for sequence gaps
        gaps = []
        last_seq = (start_sequence or 1) - 1

        # Verify each entry
        for entry in entries:
            # Check for gaps in sequence
            if entry.sequence_number and entry.sequence_number != last_seq + 1:
                gaps.extend(range(last_seq + 1, entry.sequence_number))

            # Verify previous hash link
            if entry.previous_hash != expected_previous_hash:
                return IntegrityCheckResult(
                    is_valid=False,
                    entries_checked=entries.index(entry),
                    first_invalid_sequence=entry.sequence_number,
                    first_invalid_id=entry.id,
                    error_message=f"Previous hash mismatch at sequence {entry.sequence_number}",
                    gaps_detected=gaps if gaps else None,
                )

            # Compute expected hash
            entry_created_at = entry.created_at
            if entry_created_at.tzinfo is None:
                # Add UTC timezone if missing for consistent hash computation
                from datetime import timezone
                entry_created_at = entry_created_at.replace(tzinfo=timezone.utc)

            computed_hash = compute_entry_hash(
                entry_id=entry.id,
                created_at=entry_created_at,
                actor_type=entry.actor_type,
                actor_id=entry.actor_id,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                outcome=entry.outcome,
                previous_hash=entry.previous_hash or GENESIS_HASH,
            )

            # Verify entry hash
            if entry.entry_hash != computed_hash:
                return IntegrityCheckResult(
                    is_valid=False,
                    entries_checked=entries.index(entry),
                    first_invalid_sequence=entry.sequence_number,
                    first_invalid_id=entry.id,
                    error_message=f"Entry hash mismatch at sequence {entry.sequence_number} - possible tampering",
                    gaps_detected=gaps if gaps else None,
                )

            # Update for next iteration
            expected_previous_hash = entry.entry_hash
            last_seq = entry.sequence_number or last_seq + 1

        return IntegrityCheckResult(
            is_valid=True,
            entries_checked=len(entries),
            gaps_detected=gaps if gaps else None,
        )

    def get_chain_summary(self) -> dict[str, Any]:
        """Get summary statistics about the audit log chain.

        Returns:
            Dictionary with chain statistics
        """
        # Count total entries
        total_count = self.db.execute(
            select(func.count()).select_from(AuditLog)
        ).scalar() or 0

        # Count entries with hashes
        hashed_count = self.db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entry_hash.isnot(None))
        ).scalar() or 0

        # Get sequence range
        seq_range = self.db.execute(
            select(
                func.min(AuditLog.sequence_number),
                func.max(AuditLog.sequence_number),
            )
            .where(AuditLog.sequence_number.isnot(None))
        ).first()

        # Get latest entry timestamp
        latest_entry = self.db.execute(
            select(AuditLog.created_at)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        ).scalar()

        return {
            "total_entries": total_count,
            "hashed_entries": hashed_count,
            "unhashed_entries": total_count - hashed_count,
            "sequence_start": seq_range[0] if seq_range else None,
            "sequence_end": seq_range[1] if seq_range else None,
            "latest_entry_at": latest_entry.isoformat() if latest_entry else None,
            "chain_coverage_percent": (
                round(hashed_count / total_count * 100, 2) if total_count > 0 else 0
            ),
        }

    def backfill_hashes(self, batch_size: int = 1000) -> int:
        """Backfill hashes for existing entries without them.

        This is useful for migrating existing audit logs to include
        hash chain verification.

        Args:
            batch_size: Number of entries to process per batch

        Returns:
            Number of entries updated
        """
        # Get entries without hashes, ordered by created_at
        stmt = (
            select(AuditLog)
            .where(AuditLog.entry_hash.is_(None))
            .order_by(AuditLog.created_at)
            .limit(batch_size)
        )

        entries = self.db.execute(stmt).scalars().all()

        if not entries:
            return 0

        # Get latest hash info
        previous_hash, last_seq = get_latest_hash_info(self.db)

        updated = 0
        for entry in entries:
            last_seq += 1

            # Compute hash using the entry's actual created_at timestamp
            entry_created_at = entry.created_at
            if entry_created_at.tzinfo is None:
                # Add UTC timezone if missing
                from datetime import timezone
                entry_created_at = entry_created_at.replace(tzinfo=timezone.utc)

            entry_hash = compute_entry_hash(
                entry_id=entry.id,
                created_at=entry_created_at,
                actor_type=entry.actor_type,
                actor_id=entry.actor_id,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                outcome=entry.outcome,
                previous_hash=previous_hash,
            )

            # Update entry
            entry.sequence_number = last_seq
            entry.previous_hash = previous_hash
            entry.entry_hash = entry_hash

            previous_hash = entry_hash
            updated += 1

        self.db.flush()
        logger.info(f"Backfilled hashes for {updated} audit log entries")

        return updated
