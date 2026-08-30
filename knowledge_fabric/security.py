"""Security primitives shared by retrieval and the web control plane.

The key rule is *deny before context construction*: ACL and sensitivity checks
are applied to chunks before they can reach the LLM.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass(frozen=True)
class Principal:
    user_id: str = "anonymous"
    groups: frozenset[str] = field(default_factory=frozenset)
    tenant_id: str = "local"
    authenticated: bool = False


class SecurityPolicy:
    def __init__(self, allowed_sensitivity=None, allowed_users=None, allowed_groups=None, public_access=True):
        self.allowed = set(allowed_sensitivity or ["public", "internal"])
        self.allowed_users = set(allowed_users or [])
        self.allowed_groups = set(allowed_groups or [])
        self.public_access = bool(public_access)

    def authorize_chunk(self, chunk, principal: Principal | None = None) -> bool:
        if chunk.sensitivity not in self.allowed:
            return False
        principal = principal or Principal()
        extra = chunk.extra or {}
        if extra.get("tenant_id", "local") != principal.tenant_id:
            return False
        users = set(extra.get("allowed_users") or [])
        groups = set(extra.get("allowed_groups") or [])
        if users and principal.user_id not in users:
            return False
        if groups and not (set(principal.groups) & groups):
            return False
        # Source-level ACL, configured in the pipeline policy.
        if self.allowed_users or self.allowed_groups:
            if principal.user_id in self.allowed_users:
                return True
            if set(principal.groups) & self.allowed_groups:
                return True
            return self.public_access and not self.allowed_users and not self.allowed_groups
        if not principal.authenticated and not self.public_access:
            return False
        return True

    def filter_chunks(self, chunks, principal: Principal | None = None):
        return [c for c in chunks if self.authorize_chunk(c, principal)]

    def allowed_item_ids(self, chunks, principal: Principal | None = None):
        return {c.item_id for c in chunks if self.authorize_chunk(c, principal)}

    def allowed_chunk_ids(self, chunks, principal: Principal | None = None):
        """Chunk-granularity authorization, correct even when a single file
        (item_id) contains chunks of different sensitivity. allowed_item_ids
        is item-level and was found to leak: if any chunk in a file is
        authorized, every chunk sharing that item_id passes an item_id-based
        filter, including a specific confidential chunk in an otherwise
        internal file. Retrieval filtering must use this method, not
        allowed_item_ids, for that reason."""
        return {c.chunk_id for c in chunks if self.authorize_chunk(c, principal)}


class ConstantTimeSecret:
    """Small helper for API-key comparisons; never logs the secret."""

    @staticmethod
    def matches(candidate: str, expected: str) -> bool:
        if not candidate or not expected:
            return False
        return hmac.compare_digest(
            hashlib.sha256(candidate.encode()).digest(),
            hashlib.sha256(expected.encode()).digest(),
        )


class RateLimiter:
    """Process-local fixed-window limiter.

    This is sufficient for a single local/EC2 process. Multi-instance
    deployments should replace it with a shared Redis/API-gateway limiter.
    """

    def __init__(self, limit=60, window_seconds=60):
        self.limit = max(1, int(limit))
        self.window = max(1, int(window_seconds))
        self._buckets = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            start, count = self._buckets.get(key, (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            if count >= self.limit:
                self._buckets[key] = (start, count)
                return False
            self._buckets[key] = (start, count + 1)
            # Avoid unbounded growth.
            if len(self._buckets) > 10000:
                cutoff = now - self.window
                self._buckets = {k: v for k, v in self._buckets.items() if v[0] >= cutoff}
            return True


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)

class RedisRateLimiter(RateLimiter):
    """Shared fixed-window limiter for multi-instance deployments.

    Requires the optional `redis` package and KF_REDIS_URL. Falls back to
    local behavior only when explicitly requested by the caller.
    """
    def __init__(self, redis_url, limit=60, window_seconds=60):
        import redis
        self.client=redis.from_url(redis_url, decode_responses=True)
        self.limit=max(1,int(limit)); self.window=max(1,int(window_seconds))

    def allow(self, key):
        bucket=int(time.time()//self.window)
        redis_key=f"kf:rate:{bucket}:{key}"
        count=self.client.incr(redis_key)
        if count == 1: self.client.expire(redis_key,self.window+2)
        return count <= self.limit
