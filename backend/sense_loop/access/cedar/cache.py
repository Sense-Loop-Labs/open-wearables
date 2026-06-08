"""In-memory policy caching with TTL.

Provides caching for Cedar policy evaluations to reduce database load.
Cache entries have a time-to-live and can be invalidated on policy changes.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from uuid import UUID

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry with expiration."""

    value: T
    expires_at: float
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > self.expires_at


class PolicyCache:
    """Thread-safe in-memory cache for policy evaluations.

    Provides caching with TTL, automatic expiration, and selective
    invalidation for policy changes.
    """

    def __init__(
        self,
        default_ttl_seconds: int = 300,  # 5 minutes
        max_entries: int = 10000,
        cleanup_interval_seconds: int = 60,
    ):
        """Initialize the cache.

        Args:
            default_ttl_seconds: Default TTL for cache entries
            max_entries: Maximum number of entries before eviction
            cleanup_interval_seconds: How often to run cleanup
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._cleanup_interval = cleanup_interval_seconds
        self._last_cleanup = time.time()

        # Statistics
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl

        with self._lock:
            # Run cleanup if needed
            self._maybe_cleanup()

            # Evict if at capacity
            if len(self._cache) >= self._max_entries:
                self._evict_oldest()

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
            )

    def delete(self, key: str) -> bool:
        """Delete a specific key from the cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was found and deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern.

        Pattern matching supports:
        - Prefix match: "practitioner:123:*" matches all keys starting with "practitioner:123:"
        - Suffix match: "*:patient" matches all keys ending with ":patient"

        Args:
            pattern: Pattern to match (supports * wildcard at start or end)

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_delete = []

            if pattern.endswith("*"):
                prefix = pattern[:-1]
                for key in self._cache:
                    if key.startswith(prefix):
                        keys_to_delete.append(key)
            elif pattern.startswith("*"):
                suffix = pattern[1:]
                for key in self._cache:
                    if key.endswith(suffix):
                        keys_to_delete.append(key)
            else:
                # Exact match
                if pattern in self._cache:
                    keys_to_delete.append(pattern)

            for key in keys_to_delete:
                del self._cache[key]

            logger.debug(
                f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}"
            )
            return len(keys_to_delete)

    def invalidate_for_practitioner(self, practitioner_id: UUID) -> int:
        """Invalidate all cache entries for a practitioner.

        Args:
            practitioner_id: The practitioner ID

        Returns:
            Number of entries invalidated
        """
        return self.invalidate_by_pattern(f"practitioner:{practitioner_id}:*")

    def invalidate_for_organization(self, organization_id: UUID) -> int:
        """Invalidate all cache entries for an organization.

        Args:
            organization_id: The organization ID

        Returns:
            Number of entries invalidated
        """
        return self.invalidate_by_pattern(f"*:org:{organization_id}:*")

    def invalidate_for_policy(self, policy_code: str) -> int:
        """Invalidate all cache entries that might be affected by a policy.

        This is a broad invalidation since policy changes can affect many users.

        Args:
            policy_code: The policy code

        Returns:
            Number of entries invalidated
        """
        # For policy changes, we need to clear more broadly
        # since we don't track which entries used which policies
        return self.clear()

    def clear(self) -> int:
        """Clear the entire cache.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.debug(f"Cleared {count} cache entries")
            return count

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "default_ttl_seconds": self._default_ttl,
            }

    def _maybe_cleanup(self) -> None:
        """Run cleanup if enough time has passed."""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self._cache.items() if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _evict_oldest(self) -> None:
        """Evict the oldest entry to make room for new ones."""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at,
        )
        del self._cache[oldest_key]


# Global policy cache instance
_policy_cache: PolicyCache | None = None


def get_policy_cache() -> PolicyCache:
    """Get the global policy cache instance.

    Returns:
        The global PolicyCache instance
    """
    global _policy_cache
    if _policy_cache is None:
        _policy_cache = PolicyCache()
    return _policy_cache


def make_cache_key(
    practitioner_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    organization_id: UUID,
) -> str:
    """Create a cache key for an authorization check.

    Args:
        practitioner_id: The practitioner ID
        action: The action being performed
        resource_type: The resource type
        resource_id: The resource ID (or None)
        organization_id: The organization ID

    Returns:
        Cache key string
    """
    resource_str = str(resource_id) if resource_id else "type"
    return f"practitioner:{practitioner_id}:org:{organization_id}:{resource_type}:{action}:{resource_str}"


def make_field_filter_cache_key(
    practitioner_id: UUID,
    resource_type: str,
    organization_id: UUID,
) -> str:
    """Create a cache key for field filter restrictions.

    Args:
        practitioner_id: The practitioner ID
        resource_type: The resource type
        organization_id: The organization ID

    Returns:
        Cache key string
    """
    return f"field_filter:practitioner:{practitioner_id}:org:{organization_id}:{resource_type}"


class CachedCedarEngine:
    """Wrapper around CedarEngine that adds caching.

    Provides the same interface as CedarEngine but caches authorization
    decisions for improved performance.
    """

    def __init__(self, engine: "CedarEngine", cache: PolicyCache | None = None):
        """Initialize the cached engine.

        Args:
            engine: The underlying CedarEngine
            cache: Optional PolicyCache (uses global cache if not provided)
        """
        from .engine import CedarEngine

        self._engine = engine
        self._cache = cache or get_policy_cache()

    def is_authorized(
        self,
        practitioner: "Practitioner",
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        organization_id: UUID,
        context: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> "CedarAuthorizationResult":
        """Check authorization with caching.

        Args:
            practitioner: The practitioner
            action: The action
            resource_type: The resource type
            resource_id: The resource ID
            organization_id: The organization ID
            context: Additional context
            use_cache: Whether to use caching

        Returns:
            CedarAuthorizationResult
        """
        from .engine import CedarAuthorizationResult

        if not use_cache:
            return self._engine.is_authorized(
                practitioner, action, resource_type, resource_id, organization_id, context
            )

        cache_key = make_cache_key(
            practitioner.id, action, resource_type, resource_id, organization_id
        )

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Compute result
        result = self._engine.is_authorized(
            practitioner, action, resource_type, resource_id, organization_id, context
        )

        # Cache the result (shorter TTL for BTG access)
        ttl = 60 if result.btg_access else None  # 1 minute for BTG, default otherwise
        self._cache.set(cache_key, result, ttl)

        return result

    def invalidate_cache(
        self,
        practitioner_id: UUID | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        """Invalidate cache entries.

        Args:
            practitioner_id: Optional practitioner to invalidate
            organization_id: Optional organization to invalidate
        """
        if practitioner_id:
            self._cache.invalidate_for_practitioner(practitioner_id)
        if organization_id:
            self._cache.invalidate_for_organization(organization_id)
        if not practitioner_id and not organization_id:
            self._cache.clear()

        # Also call underlying engine invalidation
        self._engine.invalidate_cache(practitioner_id, organization_id)


# Type hints for imports
if True:  # TYPE_CHECKING workaround for runtime imports
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from sense_loop.models import Practitioner
        from .engine import CedarAuthorizationResult, CedarEngine
