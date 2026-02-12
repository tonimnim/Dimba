import os
import pytest

os.environ["FLASK_ENV"] = "testing"

from app import create_app
from app.extensions import db as _db
from app.models.user import User, UserRole


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    yield app


@pytest.fixture(autouse=True)
def tables(app):
    """Create all tables before each test, drop after."""
    with app.app_context():
        _db.create_all()
        yield
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    with app.app_context():
        user = User(
            email="testadmin@premia.co.ke",
            first_name="Test",
            last_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        user.set_password("Admin@2026")
        _db.session.add(user)
        _db.session.commit()
        return user


@pytest.fixture
def admin_headers(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": "testadmin@premia.co.ke", "password": "Admin@2026"},
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def coach_user(app):
    with app.app_context():
        from app.models.region import Region
        from app.models.county import County
        from app.models.team import Team, TeamCategory

        region = Region(name="TestRegion", code="TST")
        _db.session.add(region)
        _db.session.flush()

        county = County(name="TestCounty", code=99, region_id=region.id)
        _db.session.add(county)
        _db.session.flush()

        team = Team(
            name="Coach FC",
            county_id=county.id,
            region_id=region.id,
            category=TeamCategory.MEN,
        )
        _db.session.add(team)
        _db.session.flush()

        user = User(
            email="coach@premia.co.ke",
            first_name="Test",
            last_name="Coach",
            role=UserRole.COACH,
            team_id=team.id,
        )
        user.set_password("Coach@2026")
        _db.session.add(user)
        _db.session.commit()
        return user


@pytest.fixture
def coach_headers(client, coach_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": "coach@premia.co.ke", "password": "Coach@2026"},
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
