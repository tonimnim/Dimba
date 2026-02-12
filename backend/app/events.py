import json
import queue
import threading
from datetime import datetime, timezone


class EventBus:
    """In-memory pub/sub for SSE. Each subscriber gets a Queue."""

    def __init__(self):
        self._subscribers = []
        self._lock = threading.Lock()

    def subscribe(self):
        """Create a new subscriber queue."""
        q = queue.Queue(maxsize=50)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        """Remove a subscriber queue."""
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not q]

    def publish(self, event_type, data):
        """Push event to all subscribers. Drops full queues."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        msg = json.dumps(event)
        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    @property
    def subscriber_count(self):
        with self._lock:
            return len(self._subscribers)

    def clear(self):
        """Remove all subscribers. Used in tests."""
        with self._lock:
            self._subscribers.clear()


event_bus = EventBus()
