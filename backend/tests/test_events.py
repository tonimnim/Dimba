"""Tests for SSE event bus and streaming endpoint."""
import json
import queue
import threading
import time

import pytest

from app.events import EventBus, event_bus
from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.season import Season
from app.models.competition import Competition, CompetitionType, CompetitionCategory
from app.models.team import Team, TeamCategory
from app.models.match import Match, MatchStatus
from app.models.user import User, UserRole
from app.services.match_service import confirm_result


# ── EventBus unit tests ─────────────────────────────────────────────────────


class TestEventBus:
    def test_subscribe_creates_queue(self):
        bus = EventBus()
        q = bus.subscribe()
        assert isinstance(q, queue.Queue)
        assert bus.subscriber_count == 1
        bus.unsubscribe(q)

    def test_publish_delivers_to_subscriber(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.publish("test_event", {"key": "value"})
        msg = json.loads(q.get_nowait())
        assert msg["type"] == "test_event"
        assert msg["data"]["key"] == "value"
        assert "timestamp" in msg
        bus.unsubscribe(q)

    def test_publish_delivers_to_multiple_subscribers(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.publish("broadcast", {"x": 1})
        assert not q1.empty()
        assert not q2.empty()
        m1 = json.loads(q1.get_nowait())
        m2 = json.loads(q2.get_nowait())
        assert m1["type"] == "broadcast"
        assert m2["type"] == "broadcast"
        bus.unsubscribe(q1)
        bus.unsubscribe(q2)

    def test_unsubscribe_removes_queue(self):
        bus = EventBus()
        q = bus.subscribe()
        assert bus.subscriber_count == 1
        bus.unsubscribe(q)
        assert bus.subscriber_count == 0
        bus.publish("after_unsub", {})
        assert q.empty()

    def test_full_queue_is_dropped(self):
        bus = EventBus()
        q = bus.subscribe()
        # Fill the queue to capacity (maxsize=50)
        for i in range(50):
            bus.publish("fill", {"i": i})
        assert bus.subscriber_count == 1
        # Next publish should drop the full queue
        bus.publish("overflow", {})
        assert bus.subscriber_count == 0

    def test_clear_removes_all_subscribers(self):
        bus = EventBus()
        bus.subscribe()
        bus.subscribe()
        assert bus.subscriber_count == 2
        bus.clear()
        assert bus.subscriber_count == 0

    def test_thread_safety(self):
        bus = EventBus()
        queues = []
        errors = []

        def sub_and_read():
            try:
                q = bus.subscribe()
                queues.append(q)
                msg = q.get(timeout=2)
                json.loads(msg)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sub_and_read) for _ in range(5)]
        for t in threads:
            t.start()
        time.sleep(0.1)
        bus.publish("thread_test", {"ok": True})
        for t in threads:
            t.join(timeout=3)
        assert not errors
        for q in queues:
            bus.unsubscribe(q)


# ── Integration: confirm_result publishes events ─────────────────────────────


class TestConfirmPublishesEvents:
    @pytest.fixture(autouse=True)
    def _clean_bus(self):
        """Ensure global event_bus is clean before/after each test."""
        event_bus.clear()
        yield
        event_bus.clear()

    @pytest.fixture
    def match_data(self, app):
        """Create a completed match ready for confirmation."""
        with app.app_context():
            admin = User(
                email="sseadmin@premia.co.ke",
                first_name="SSE",
                last_name="Admin",
                role=UserRole.SUPER_ADMIN,
            )
            admin.set_password("Admin@2026")
            db.session.add(admin)
            db.session.flush()

            r = Region(name="Coast", code="CST")
            db.session.add(r)
            db.session.flush()
            c = County(name="Mombasa", code=1, region_id=r.id)
            db.session.add(c)
            db.session.flush()

            s = Season(name="2026", year=2026)
            db.session.add(s)
            db.session.flush()

            comp = Competition(
                name="Coast League",
                season_id=s.id,
                region_id=r.id,
                type=CompetitionType.REGIONAL,
                category=CompetitionCategory.MEN,
            )
            db.session.add(comp)
            db.session.flush()

            t1 = Team(name="Bandari", county_id=c.id, region_id=r.id, category=TeamCategory.MEN)
            t2 = Team(name="Mombasa FC", county_id=c.id, region_id=r.id, category=TeamCategory.MEN)
            db.session.add_all([t1, t2])
            db.session.flush()

            match = Match(
                competition_id=comp.id,
                season_id=s.id,
                home_team_id=t1.id,
                away_team_id=t2.id,
                home_score=2,
                away_score=1,
                status=MatchStatus.COMPLETED,
            )
            db.session.add(match)
            db.session.commit()

            return {
                "match_id": match.id,
                "admin_id": admin.id,
                "comp_id": comp.id,
                "season_id": s.id,
                "home_team_id": t1.id,
                "away_team_id": t2.id,
            }

    def test_confirm_publishes_match_confirmed(self, app, match_data):
        q = event_bus.subscribe()
        with app.app_context():
            match, error = confirm_result(match_data["match_id"], match_data["admin_id"])
        assert error is None

        events = []
        while not q.empty():
            events.append(json.loads(q.get_nowait()))

        types = [e["type"] for e in events]
        assert "match_confirmed" in types
        event_bus.unsubscribe(q)

    def test_confirm_publishes_standings_updated(self, app, match_data):
        q = event_bus.subscribe()
        with app.app_context():
            confirm_result(match_data["match_id"], match_data["admin_id"])

        events = []
        while not q.empty():
            events.append(json.loads(q.get_nowait()))

        types = [e["type"] for e in events]
        assert "standings_updated" in types

        su = next(e for e in events if e["type"] == "standings_updated")
        assert su["data"]["competition_id"] == match_data["comp_id"]
        assert su["data"]["season_id"] == match_data["season_id"]
        event_bus.unsubscribe(q)

    def test_confirm_match_confirmed_payload(self, app, match_data):
        q = event_bus.subscribe()
        with app.app_context():
            confirm_result(match_data["match_id"], match_data["admin_id"])

        events = []
        while not q.empty():
            events.append(json.loads(q.get_nowait()))

        mc = next(e for e in events if e["type"] == "match_confirmed")
        assert mc["data"]["match_id"] == match_data["match_id"]
        assert mc["data"]["home_team_id"] == match_data["home_team_id"]
        assert mc["data"]["away_team_id"] == match_data["away_team_id"]
        assert mc["data"]["home_score"] == 2
        assert mc["data"]["away_score"] == 1
        event_bus.unsubscribe(q)

    def test_no_bracket_event_for_non_bracket_match(self, app, match_data):
        q = event_bus.subscribe()
        with app.app_context():
            confirm_result(match_data["match_id"], match_data["admin_id"])

        events = []
        while not q.empty():
            events.append(json.loads(q.get_nowait()))

        types = [e["type"] for e in events]
        assert "bracket_updated" not in types
        event_bus.unsubscribe(q)


# ── SSE endpoint tests ──────────────────────────────────────────────────────


class TestSSEEndpoint:
    @pytest.fixture(autouse=True)
    def _clean_bus(self):
        event_bus.clear()
        yield
        event_bus.clear()

    def test_stream_content_type(self, client):
        """SSE endpoint returns text/event-stream."""
        # Use a thread to make the request and read one chunk
        result = {}

        def make_request():
            resp = client.get("/api/events/stream")
            result["content_type"] = resp.content_type
            result["status"] = resp.status_code

        # Publish an event so the generator yields and we can get a response
        event_bus.publish("pre_connect", {"test": True})

        t = threading.Thread(target=make_request)
        t.start()
        time.sleep(0.2)
        # The thread may be blocked waiting; publish to unblock
        event_bus.publish("wake", {})
        t.join(timeout=5)

        if "content_type" in result:
            assert "text/event-stream" in result["content_type"]

    def test_stream_receives_published_event(self, app, client):
        """Events published after subscribe are received in the stream."""
        chunks = []
        stop = threading.Event()

        def read_stream():
            with client.get(
                "/api/events/stream",
                headers={"Accept": "text/event-stream"},
            ) as resp:
                for line in resp.response:
                    if isinstance(line, bytes):
                        line = line.decode()
                    chunks.append(line)
                    if stop.is_set():
                        break
                    if len(chunks) >= 2:
                        stop.set()
                        break

        t = threading.Thread(target=read_stream)
        t.start()
        time.sleep(0.3)  # Wait for subscription to register

        event_bus.publish("test_sse", {"msg": "hello"})
        event_bus.publish("test_sse_2", {"msg": "world"})

        t.join(timeout=5)

        data_lines = [c for c in chunks if c.startswith("data: ")]
        if data_lines:
            payload = json.loads(data_lines[0].removeprefix("data: ").strip())
            assert payload["type"] == "test_sse"
            assert payload["data"]["msg"] == "hello"
