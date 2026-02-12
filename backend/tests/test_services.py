from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.season import Season
from app.models.competition import Competition, CompetitionType, CompetitionCategory
from app.models.team import Team, TeamCategory, TeamStatus
from app.models.player import Player, PlayerPosition
from app.models.match import Match, MatchStatus
from app.models.user import User, UserRole
from app.services.match_service import submit_result, confirm_result
from app.services.transfer_service import initiate_transfer, approve_transfer, reject_transfer
from app.services.standings import recalculate_standings


def _seed_match_fixture():
    """Create region, county, season, competition, two teams, and a match."""
    region = Region(name="Test Region", code="TST")
    db.session.add(region)
    db.session.flush()

    county = County(name="Test County", code=99, region_id=region.id)
    db.session.add(county)
    db.session.flush()

    season = Season(name="2026", year=2026, is_active=True)
    db.session.add(season)
    db.session.flush()

    comp = Competition(
        name="Test League",
        type=CompetitionType.REGIONAL,
        category=CompetitionCategory.MEN,
        season_id=season.id,
        region_id=region.id,
    )
    db.session.add(comp)
    db.session.flush()

    home = Team(name="Home FC", county_id=county.id, region_id=region.id,
                category=TeamCategory.MEN, status=TeamStatus.ACTIVE)
    away = Team(name="Away FC", county_id=county.id, region_id=region.id,
                category=TeamCategory.MEN, status=TeamStatus.ACTIVE)
    db.session.add_all([home, away])
    db.session.flush()

    user = User(email="ref@test.co.ke", first_name="Ref", last_name="Test",
                role=UserRole.SUPER_ADMIN)
    user.set_password("Ref@12345")
    db.session.add(user)
    db.session.flush()

    match = Match(
        competition_id=comp.id, season_id=season.id,
        home_team_id=home.id, away_team_id=away.id,
        status=MatchStatus.SCHEDULED,
    )
    db.session.add(match)
    db.session.flush()

    return match, user, comp, season, home, away


def test_submit_result(app):
    with app.app_context():
        match, user, *_ = _seed_match_fixture()

        result, error = submit_result(match.id, 2, 1, user.id)
        assert error is None
        assert result.home_score == 2
        assert result.away_score == 1
        assert result.status == MatchStatus.COMPLETED


def test_submit_result_wrong_status(app):
    with app.app_context():
        match, user, *_ = _seed_match_fixture()
        submit_result(match.id, 2, 1, user.id)

        # Cannot submit again — already COMPLETED
        result, error = submit_result(match.id, 3, 0, user.id)
        assert result is None
        assert "scheduled" in error.lower()


def test_confirm_result(app):
    with app.app_context():
        match, user, *_ = _seed_match_fixture()
        submit_result(match.id, 1, 1, user.id)

        result, error = confirm_result(match.id, user.id)
        assert error is None
        assert result.status == MatchStatus.CONFIRMED


def test_standings_recalculation(app):
    with app.app_context():
        match, user, comp, season, home, away = _seed_match_fixture()
        submit_result(match.id, 3, 0, user.id)
        confirm_result(match.id, user.id)

        from app.models.standing import Standing

        standings = Standing.query.filter_by(
            competition_id=comp.id, season_id=season.id
        ).order_by(Standing.points.desc()).all()

        assert len(standings) == 2

        winner = standings[0]
        loser = standings[1]
        assert winner.team_id == home.id
        assert winner.points == 3
        assert winner.won == 1
        assert winner.goals_for == 3
        assert loser.points == 0
        assert loser.lost == 1


def test_transfer_flow(app):
    with app.app_context():
        match, user, comp, season, home, away = _seed_match_fixture()

        player = Player(
            first_name="John", last_name="Doe",
            position=PlayerPosition.FWD,
            team_id=home.id,
        )
        db.session.add(player)
        db.session.flush()

        # Initiate transfer
        data = {
            "player_id": player.id,
            "from_team_id": home.id,
            "to_team_id": away.id,
            "fee": 1000,
            "reason": "Transfer",
        }
        transfer, error = initiate_transfer(data, user.id)
        assert error is None
        assert transfer.status.value == "pending"

        # Approve
        transfer, error = approve_transfer(transfer.id, user.id)
        assert error is None
        assert transfer.status.value == "completed"
        assert player.team_id == away.id


def test_transfer_reject(app):
    with app.app_context():
        match, user, comp, season, home, away = _seed_match_fixture()

        player = Player(
            first_name="Jane", last_name="Doe",
            position=PlayerPosition.MID,
            team_id=home.id,
        )
        db.session.add(player)
        db.session.flush()

        data = {
            "player_id": player.id,
            "from_team_id": home.id,
            "to_team_id": away.id,
        }
        transfer, _ = initiate_transfer(data, user.id)

        transfer, error = reject_transfer(transfer.id, user.id)
        assert error is None
        assert transfer.status.value == "rejected"
        # Player stays on original team
        assert player.team_id == home.id


def test_transfer_wrong_team(app):
    with app.app_context():
        match, user, comp, season, home, away = _seed_match_fixture()

        player = Player(
            first_name="Bob", last_name="Smith",
            position=PlayerPosition.DEF,
            team_id=away.id,
        )
        db.session.add(player)
        db.session.flush()

        data = {
            "player_id": player.id,
            "from_team_id": home.id,  # Wrong — player is on 'away'
            "to_team_id": away.id,
        }
        transfer, error = initiate_transfer(data, user.id)
        assert transfer is None
        assert "does not belong" in error
