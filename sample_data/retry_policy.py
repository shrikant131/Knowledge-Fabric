"""Sample service module used to demo code ingestion."""
import time


class RetryPolicy:
    """Encapsulates retry/backoff behavior for connector fetch calls."""

    def __init__(self, max_attempts: int = 5, base_delay_seconds: float = 2.0):
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def run(self, func, *args, **kwargs):
        """Run func with exponential backoff, raising after max_attempts."""
        last_exc = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                delay = self.base_delay_seconds * (2 ** (attempt - 1))
                time.sleep(delay)
        raise last_exc


def get_user_by_id(user_id: str) -> dict:
    """Fetch a user record. Placeholder for a real DB/service call."""
    if not user_id:
        raise ValueError("user_id is required")
    return {"id": user_id, "name": "Sample User"}


class DeadLetterQueue:
    """Holds events that exhausted retries, for manual replay."""

    def __init__(self):
        self._items = []

    def push(self, event: dict, error: str):
        self._items.append({"event": event, "error": error})

    def drain(self):
        items, self._items = self._items, []
        return items
