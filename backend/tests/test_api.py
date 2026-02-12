from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.season import Season
from app.models.team import Team, TeamCategory
from app.models.player import Player, PlayerPosition
from app.models.match import Match, MatchStatus
from app.models.competition import Competition, CompetitionType, CompetitionCategory, competition_teams
from app.models.standing import Standing
from app.models.user import User


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "healthy"


def test_get_regions(client):
    # Seed a region
    region = Region(name="Central", code="CEN")
    db.session.add(region)
    db.session.flush()

    resp = client.get("/api/regions")
    assert resp.status_code == 200
    regions = resp.get_json()["regions"]
    assert len(regions) >= 1
    assert any(r["code"] == "CEN" for r in regions)


def test_get_region_detail(client):
    region = Region(name="Coast", code="CST")
    db.session.add(region)
    db.session.flush()

    resp = client.get(f"/api/regions/{region.id}")
    assert resp.status_code == 200
    assert resp.get_json()["region"]["name"] == "Coast"


def test_get_region_not_found(client):
    resp = client.get("/api/regions/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_get_counties_filtered(client):
    region = Region(name="Nyanza", code="NYZ")
    db.session.add(region)
    db.session.flush()

    county = County(name="Kisumu", code=25, region_id=region.id)
    db.session.add(county)
    db.session.flush()

    resp = client.get(f"/api/counties?region_id={region.id}")
    assert resp.status_code == 200
    counties = resp.get_json()["counties"]
    assert len(counties) == 1
    assert counties[0]["name"] == "Kisumu"


def test_create_season_requires_admin(client, coach_headers):
    resp = client.post(
        "/api/seasons",
        headers=coach_headers,
        json={"name": "2026 Season", "year": 2026},
    )
    assert resp.status_code == 403


def test_create_season_success(client, admin_headers):
    resp = client.post(
        "/api/seasons",
        headers=admin_headers,
        json={"name": "2026 Season", "year": 2026},
    )
    assert resp.status_code == 201
    assert resp.get_json()["season"]["name"] == "2026 Season"


def test_create_season_validation(client, admin_headers):
    resp = client.post(
        "/api/seasons",
        headers=admin_headers,
        json={"name": "", "year": 1800},
    )
    assert resp.status_code == 400
    assert "messages" in resp.get_json()


def test_create_team_validation(client, admin_headers):
    # missing required fields
    resp = client.post(
        "/api/teams",
        headers=admin_headers,
        json={"name": "Test FC"},
    )
    assert resp.status_code == 400


def test_get_standings_missing_params(client):
    resp = client.get("/api/standings")
    assert resp.status_code == 400
    assert "required" in resp.get_json()["error"]


def test_get_user_idor_protection(app, client, admin_user, coach_headers):
    """Coach should not be able to view admin's profile."""
    with app.app_context():
        from app.models.user import User
        admin = User.query.filter_by(email="testadmin@premia.co.ke").first()
        admin_id = admin.id

    resp = client.get(
        f"/api/users/{admin_id}",
        headers=coach_headers,
    )
    assert resp.status_code == 403


def test_method_not_allowed(client):
    resp = client.delete("/api/regions")
    assert resp.status_code == 405
    assert "error" in resp.get_json()


# ─── Player Delete Tests ────────────────────────────────────────────────────


def test_delete_player_as_admin(client, admin_headers, coach_user):
    """Admin can delete any player."""
    with client.application.app_context():
        coach = User.query.filter_by(email="coach@premia.co.ke").first()
        player = Player(
            first_name="Del",
            last_name="Admin",
            position=PlayerPosition.FWD,
            team_id=coach.team_id,
        )
        db.session.add(player)
        db.session.commit()
        pid = player.id

    resp = client.delete(f"/api/players/{pid}", headers=admin_headers)
    assert resp.status_code == 200
    assert "deleted" in resp.get_json()["message"].lower()


def test_delete_player_as_coach_own_team(client, coach_headers, coach_user):
    """Coach can delete a player on their own team."""
    with client.application.app_context():
        coach = User.query.filter_by(email="coach@premia.co.ke").first()
        player = Player(
            first_name="Own",
            last_name="Player",
            position=PlayerPosition.DEF,
            team_id=coach.team_id,
        )
        db.session.add(player)
        db.session.commit()
        pid = player.id

    resp = client.delete(f"/api/players/{pid}", headers=coach_headers)
    assert resp.status_code == 200


def test_delete_player_as_coach_other_team(app, client, coach_headers, admin_user, coach_user):
    """Coach cannot delete a player on another team."""
    with app.app_context():
        region = Region.query.first()
        county = County.query.first()
        other_team = Team(
            name="Other FC", county_id=county.id, region_id=region.id,
            category=TeamCategory.MEN,
        )
        db.session.add(other_team)
        db.session.flush()

        player = Player(
            first_name="Other",
            last_name="Player",
            position=PlayerPosition.MID,
            team_id=other_team.id,
        )
        db.session.add(player)
        db.session.commit()
        pid = player.id

    resp = client.delete(f"/api/players/{pid}", headers=coach_headers)
    assert resp.status_code == 404


def test_delete_player_not_found(client, admin_headers):
    resp = client.delete("/api/players/99999", headers=admin_headers)
    assert resp.status_code == 404


# ─── Coach My-Team Endpoint Tests ───────────────────────────────────────────


def test_coach_my_team(app, client, coach_headers, coach_user):
    """Coach can fetch their team info."""
    resp = client.get("/api/coach/my-team", headers=coach_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["team"]["name"] == "Coach FC"
    assert isinstance(data["players"], list)


def test_coach_my_team_with_season(app, client, coach_headers, coach_user):
    """Coach my-team returns competition/standing/next_match when season active."""
    with app.app_context():
        coach = User.query.filter_by(email="coach@premia.co.ke").first()
        team_id = coach.team_id

        season = Season(name="2026", year=2026, is_active=True)
        db.session.add(season)
        db.session.flush()

        region = Region.query.first()
        comp = Competition(
            name="Regional League",
            type=CompetitionType.REGIONAL,
            category=CompetitionCategory.MEN,
            season_id=season.id,
            region_id=region.id,
        )
        db.session.add(comp)
        db.session.flush()

        # Add team to competition
        db.session.execute(
            competition_teams.insert().values(
                competition_id=comp.id, team_id=team_id
            )
        )

        standing = Standing(
            team_id=team_id,
            competition_id=comp.id,
            season_id=season.id,
            played=5, won=3, drawn=1, lost=1,
            goals_for=10, goals_against=5,
            goal_difference=5, points=10,
        )
        db.session.add(standing)

        # Create another team for the match
        county = County.query.first()
        opp = Team(
            name="Opponent FC",
            county_id=county.id,
            region_id=region.id,
            category=TeamCategory.MEN,
        )
        db.session.add(opp)
        db.session.flush()

        match = Match(
            competition_id=comp.id,
            season_id=season.id,
            home_team_id=team_id,
            away_team_id=opp.id,
            status=MatchStatus.SCHEDULED,
        )
        db.session.add(match)
        db.session.commit()

    resp = client.get("/api/coach/my-team", headers=coach_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["competition"]["name"] == "Regional League"
    assert data["standing"]["points"] == 10
    assert data["next_match"] is not None
    assert data["season"]["name"] == "2026"


def test_coach_my_team_requires_coach_role(client, admin_headers):
    """Admin cannot access coach endpoint."""
    resp = client.get("/api/coach/my-team", headers=admin_headers)
    assert resp.status_code == 403
