"""Tests for fixture scheduling algorithms and API endpoints."""
import math
from collections import Counter
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.season import Season
from app.models.competition import Competition, CompetitionType, CompetitionCategory
from app.models.team import Team, TeamCategory
from app.models.match import Match, MatchStage, MatchStatus
from app.models.standing import Standing
from app.services.scheduler_service import (
    generate_round_robin,
    generate_cl_groups,
    advance_cl_knockout,
    generate_cl_knockout_bracket,
    generate_cup_draw,
    advance_bracket_winner,
    get_bracket,
)
from app.models.user import User, UserRole
from app.services.standings import recalculate_standings
from app.services.match_service import confirm_result


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_id(app):
    """Create an admin user and return their ID (avoids detached instance issues)."""
    with app.app_context():
        user = User(
            email="schedadmin@premia.co.ke",
            first_name="Sched",
            last_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        user.set_password("Admin@2026")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def base_data(app):
    """Create a region, county, and season. Returns dict of IDs."""
    with app.app_context():
        r = Region(name="Nairobi", code="NBI")
        db.session.add(r)
        db.session.flush()
        c = County(name="Nairobi County", code=47, region_id=r.id)
        db.session.add(c)
        db.session.flush()
        s = Season(name="2026 Season", year=2026)
        db.session.add(s)
        db.session.commit()
        return {"region_id": r.id, "county_id": c.id, "season_id": s.id}


@pytest.fixture
def regional_comp(app, base_data):
    """Regional competition with 8 teams (all same county — legacy tests)."""
    with app.app_context():
        comp = Competition(
            name="Nairobi Regional League",
            type=CompetitionType.REGIONAL,
            category=CompetitionCategory.MEN,
            season_id=base_data["season_id"],
            region_id=base_data["region_id"],
        )
        db.session.add(comp)
        db.session.flush()

        team_ids = []
        for i in range(1, 9):
            t = Team(
                name=f"Team {i}",
                county_id=base_data["county_id"],
                region_id=base_data["region_id"],
                category=TeamCategory.MEN,
            )
            db.session.add(t)
            db.session.flush()
            comp.teams.append(t)
            team_ids.append(t.id)

        db.session.commit()
        return {
            "comp_id": comp.id,
            "team_ids": team_ids,
            "season_id": base_data["season_id"],
        }


@pytest.fixture
def multi_county_comp(app, base_data):
    """Regional competition with 8 teams across 3 counties.

    County A: teams 1-3 (3 teams)
    County B: teams 4-6 (3 teams)
    County C: teams 7-8 (2 teams)

    This lets us verify that early matchdays prioritise intra-county matches.
    """
    with app.app_context():
        region_id = base_data["region_id"]

        county_a_id = base_data["county_id"]  # already exists
        county_b = County(name="County B", code=48, region_id=region_id)
        county_c = County(name="County C", code=49, region_id=region_id)
        db.session.add_all([county_b, county_c])
        db.session.flush()

        comp = Competition(
            name="Multi-County League",
            type=CompetitionType.REGIONAL,
            category=CompetitionCategory.MEN,
            season_id=base_data["season_id"],
            region_id=region_id,
        )
        db.session.add(comp)
        db.session.flush()

        county_map = {
            county_a_id: ["Nyandarua FC", "Nyandarua Utd", "Nyandarua City"],
            county_b.id: ["Embu FC", "Embu Utd", "Embu City"],
            county_c.id: ["Meru FC", "Meru Utd"],
        }

        team_ids = []
        team_county = {}
        for c_id, names in county_map.items():
            for name in names:
                t = Team(
                    name=name,
                    county_id=c_id,
                    region_id=region_id,
                    category=TeamCategory.MEN,
                )
                db.session.add(t)
                db.session.flush()
                comp.teams.append(t)
                team_ids.append(t.id)
                team_county[t.id] = c_id

        db.session.commit()
        return {
            "comp_id": comp.id,
            "team_ids": team_ids,
            "team_county": team_county,
            "season_id": base_data["season_id"],
        }


@pytest.fixture
def empty_regional_comp(app, base_data):
    """Regional competition with no teams."""
    with app.app_context():
        comp = Competition(
            name="Empty League",
            type=CompetitionType.REGIONAL,
            category=CompetitionCategory.MEN,
            season_id=base_data["season_id"],
            region_id=base_data["region_id"],
        )
        db.session.add(comp)
        db.session.commit()
        return comp.id


@pytest.fixture
def cl_comp(app, base_data):
    """CL setup: 7 regions × 3 teams = 21 teams in a national competition."""
    with app.app_context():
        comp = Competition(
            name="Champions League",
            type=CompetitionType.NATIONAL,
            category=CompetitionCategory.MEN,
            season_id=base_data["season_id"],
        )
        db.session.add(comp)
        db.session.flush()

        all_team_ids = []
        for i in range(7):
            r = Region(name=f"CL Region {i+1}", code=f"CL{i+1}")
            db.session.add(r)
            db.session.flush()
            c = County(name=f"CL County {i+1}", code=50 + i, region_id=r.id)
            db.session.add(c)
            db.session.flush()
            for j in range(3):
                t = Team(
                    name=f"CL R{i+1} T{j+1}",
                    county_id=c.id,
                    region_id=r.id,
                    category=TeamCategory.MEN,
                )
                db.session.add(t)
                db.session.flush()
                comp.teams.append(t)
                all_team_ids.append(t.id)

        db.session.commit()
        return {
            "comp_id": comp.id,
            "team_ids": all_team_ids,
            "season_id": base_data["season_id"],
        }


@pytest.fixture
def cup_comp(app, base_data):
    """Cup competition (no teams yet)."""
    with app.app_context():
        comp = Competition(
            name="Kenya Cup",
            type=CompetitionType.CUP,
            category=CompetitionCategory.MEN,
            season_id=base_data["season_id"],
        )
        db.session.add(comp)
        db.session.commit()
        return {"comp_id": comp.id, "season_id": base_data["season_id"]}


def _add_cup_teams(n, comp_id, region_id, county_id):
    """Add n teams to a cup competition. Must be called inside app_context."""
    comp = db.session.get(Competition, comp_id)
    team_ids = []
    for i in range(n):
        t = Team(
            name=f"Cup Team {i+1}",
            county_id=county_id,
            region_id=region_id,
            category=TeamCategory.MEN,
        )
        db.session.add(t)
        db.session.flush()
        comp.teams.append(t)
        team_ids.append(t.id)
    db.session.commit()
    return team_ids


# ── Round-Robin Tests ────────────────────────────────────────────────────────

class TestRoundRobin:
    def test_8_teams_56_matches(self, app, regional_comp):
        with app.app_context():
            result, error = generate_round_robin(
                regional_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None
            assert len(result) == 56

    def test_14_matchdays(self, app, regional_comp):
        with app.app_context():
            result, error = generate_round_robin(
                regional_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None
            matchdays = {m.matchday for m in result}
            assert matchdays == set(range(1, 15))

    def test_4_matches_per_matchday(self, app, regional_comp):
        with app.app_context():
            result, error = generate_round_robin(
                regional_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None
            md_counts = Counter(m.matchday for m in result)
            for md, count in md_counts.items():
                assert count == 4

    def test_home_away_balance(self, app, regional_comp):
        with app.app_context():
            result, error = generate_round_robin(
                regional_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None
            home_counts = Counter(m.home_team_id for m in result)
            away_counts = Counter(m.away_team_id for m in result)
            for tid in regional_comp["team_ids"]:
                assert home_counts[tid] == 7
                assert away_counts[tid] == 7

    def test_dates_spaced_correctly(self, app, regional_comp):
        with app.app_context():
            start = date(2026, 1, 10)
            result, error = generate_round_robin(
                regional_comp["comp_id"], start, interval_days=7
            )
            assert error is None
            for match in result:
                expected = start + timedelta(days=(match.matchday - 1) * 7)
                assert match.match_date.date() == expected

    def test_standings_initialized(self, app, regional_comp):
        with app.app_context():
            generate_round_robin(regional_comp["comp_id"], date(2026, 1, 10))
            standings = Standing.query.filter_by(
                competition_id=regional_comp["comp_id"]
            ).all()
            assert len(standings) == 8
            for s in standings:
                assert s.played == 0
                assert s.points == 0

    def test_all_matches_have_league_stage(self, app, regional_comp):
        with app.app_context():
            result, error = generate_round_robin(
                regional_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None
            for m in result:
                assert m.stage == MatchStage.LEAGUE

    def test_rejects_wrong_competition_type(self, app, base_data):
        with app.app_context():
            comp = Competition(
                name="Cup", type=CompetitionType.CUP,
                category=CompetitionCategory.MEN, season_id=base_data["season_id"],
            )
            db.session.add(comp)
            db.session.commit()
            result, error = generate_round_robin(comp.id, date(2026, 1, 10))
            assert result is None
            assert "regional" in error.lower()

    def test_rejects_no_teams(self, app, empty_regional_comp):
        with app.app_context():
            result, error = generate_round_robin(
                empty_regional_comp, date(2026, 1, 10)
            )
            assert result is None
            assert "at least 2 teams" in error.lower()

    def test_rejects_duplicate_generation(self, app, regional_comp):
        with app.app_context():
            generate_round_robin(regional_comp["comp_id"], date(2026, 1, 10))
            result, error = generate_round_robin(
                regional_comp["comp_id"], date(2026, 1, 10)
            )
            assert result is None
            assert "already" in error.lower()


# ── County-Aware Scheduling Tests ────────────────────────────────────────────

class TestCountyAwareScheduling:
    """Verify that early matchdays prioritise intra-county (local) matches."""

    def test_early_matchdays_have_more_local_matches(self, app, multi_county_comp):
        """First-half matchdays should contain at least as many same-county matches
        as second-half matchdays in total."""
        with app.app_context():
            result, error = generate_round_robin(
                multi_county_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None

            team_county = multi_county_comp["team_county"]

            # Count intra-county matches per matchday
            md_local = Counter()
            for m in result:
                if team_county.get(m.home_team_id) == team_county.get(m.away_team_id):
                    md_local[m.matchday] += 1

            # Split into first half (1-7) and second half (8-14)
            first_half_local = sum(md_local[md] for md in range(1, 8))
            second_half_local = sum(md_local[md] for md in range(8, 15))

            assert first_half_local >= second_half_local

    def test_matchday_1_has_most_local_matches(self, app, multi_county_comp):
        """The very first matchday should have the highest (or tied highest)
        count of same-county matches."""
        with app.app_context():
            result, error = generate_round_robin(
                multi_county_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None

            team_county = multi_county_comp["team_county"]

            md_local = Counter()
            for m in result:
                if team_county.get(m.home_team_id) == team_county.get(m.away_team_id):
                    md_local[m.matchday] += 1

            # Matchday 1 should be >= any other first-pass matchday (1-7)
            md1_count = md_local[1]
            for md in range(2, 8):
                assert md1_count >= md_local[md], (
                    f"Matchday 1 ({md1_count} local) should have >= local matches "
                    f"than matchday {md} ({md_local[md]} local)"
                )

    def test_local_matches_decrease_over_time(self, app, multi_county_comp):
        """Intra-county match counts per matchday should be non-increasing
        across the first pass (matchdays 1 through 7)."""
        with app.app_context():
            result, error = generate_round_robin(
                multi_county_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None

            team_county = multi_county_comp["team_county"]

            md_local = Counter()
            for m in result:
                if team_county.get(m.home_team_id) == team_county.get(m.away_team_id):
                    md_local[m.matchday] += 1

            # First pass matchdays 1-7 should be sorted descending
            first_pass = [md_local[md] for md in range(1, 8)]
            for i in range(len(first_pass) - 1):
                assert first_pass[i] >= first_pass[i + 1], (
                    f"Local matches should not increase: matchday {i+1}={first_pass[i]}, "
                    f"matchday {i+2}={first_pass[i+1]}"
                )

    def test_round_robin_still_complete(self, app, multi_county_comp):
        """County-aware ordering must not break the round-robin: every pair
        of teams still plays each other exactly twice (home and away)."""
        with app.app_context():
            result, error = generate_round_robin(
                multi_county_comp["comp_id"], date(2026, 1, 10)
            )
            assert error is None

            team_ids = multi_county_comp["team_ids"]
            pair_counts = Counter()
            for m in result:
                pair_counts[(m.home_team_id, m.away_team_id)] += 1

            # Every ordered pair should appear exactly once
            for i, a in enumerate(team_ids):
                for j, b in enumerate(team_ids):
                    if a != b:
                        assert pair_counts[(a, b)] == 1, (
                            f"Team {a} vs {b} should play exactly once at home, "
                            f"got {pair_counts[(a, b)]}"
                        )


# ── Champions League Group Tests ─────────────────────────────────────────────

class TestCLGroups:
    def test_21_teams_7_groups_of_3(self, app, cl_comp):
        with app.app_context():
            result, error = generate_cl_groups(
                cl_comp["comp_id"], date(2026, 8, 1)
            )
            assert error is None
            groups = result["groups"]
            assert len(groups) == 7
            for letter, team_ids in groups.items():
                assert len(team_ids) == 3

    def test_no_same_region_in_group(self, app, cl_comp):
        with app.app_context():
            result, error = generate_cl_groups(
                cl_comp["comp_id"], date(2026, 8, 1)
            )
            assert error is None
            groups = result["groups"]
            for letter, team_ids in groups.items():
                teams = [db.session.get(Team, tid) for tid in team_ids]
                region_ids = [t.region_id for t in teams]
                assert len(set(region_ids)) == 3

    def test_42_group_matches(self, app, cl_comp):
        with app.app_context():
            result, error = generate_cl_groups(
                cl_comp["comp_id"], date(2026, 8, 1)
            )
            assert error is None
            assert len(result["matches"]) == 42

    def test_standings_with_group_names(self, app, cl_comp):
        with app.app_context():
            result, error = generate_cl_groups(
                cl_comp["comp_id"], date(2026, 8, 1)
            )
            assert error is None
            standings = Standing.query.filter_by(
                competition_id=cl_comp["comp_id"]
            ).all()
            assert len(standings) == 21
            group_names = {s.group_name for s in standings}
            assert group_names == {"A", "B", "C", "D", "E", "F", "G"}

    def test_rejects_wrong_type(self, app, base_data):
        with app.app_context():
            comp = Competition(
                name="Regional", type=CompetitionType.REGIONAL,
                category=CompetitionCategory.MEN, season_id=base_data["season_id"],
            )
            db.session.add(comp)
            db.session.commit()
            result, error = generate_cl_groups(comp.id, date(2026, 8, 1))
            assert result is None
            assert "national" in error.lower()

    def test_rejects_not_21_teams(self, app, base_data):
        with app.app_context():
            comp = Competition(
                name="CL", type=CompetitionType.NATIONAL,
                category=CompetitionCategory.MEN, season_id=base_data["season_id"],
            )
            db.session.add(comp)
            db.session.flush()

            for i in range(10):
                t = Team(
                    name=f"T{i}", county_id=base_data["county_id"],
                    region_id=base_data["region_id"], category=TeamCategory.MEN,
                )
                db.session.add(t)
                db.session.flush()
                comp.teams.append(t)
            db.session.commit()

            result, error = generate_cl_groups(comp.id, date(2026, 8, 1))
            assert result is None
            assert "21" in error

    def test_rejects_duplicate(self, app, cl_comp):
        with app.app_context():
            generate_cl_groups(cl_comp["comp_id"], date(2026, 8, 1))
            result, error = generate_cl_groups(
                cl_comp["comp_id"], date(2026, 8, 1)
            )
            assert result is None
            assert "already" in error.lower()


# ── CL Knockout Advancement Tests ────────────────────────────────────────────

class TestCLAdvancement:
    def _setup_confirmed_groups(self, cl_comp):
        """Generate groups and confirm all group matches with fake results."""
        generate_cl_groups(cl_comp["comp_id"], date(2026, 8, 1))
        matches = Match.query.filter_by(
            competition_id=cl_comp["comp_id"],
            stage=MatchStage.GROUP,
        ).all()
        for i, m in enumerate(matches):
            if i % 3 == 0:
                m.home_score, m.away_score = 2, 0
            elif i % 3 == 1:
                m.home_score, m.away_score = 1, 1
            else:
                m.home_score, m.away_score = 0, 1
            m.status = MatchStatus.CONFIRMED
        db.session.commit()
        recalculate_standings(cl_comp["comp_id"], cl_comp["season_id"])

    def test_8_teams_qualify(self, app, cl_comp):
        with app.app_context():
            self._setup_confirmed_groups(cl_comp)
            result, error = advance_cl_knockout(cl_comp["comp_id"])
            assert error is None
            assert len(result["qualified_team_ids"]) == 8

    def test_4_pairings(self, app, cl_comp):
        with app.app_context():
            self._setup_confirmed_groups(cl_comp)
            result, error = advance_cl_knockout(cl_comp["comp_id"])
            assert error is None
            assert len(result["pairings"]) == 4

    def test_all_qualified_are_unique(self, app, cl_comp):
        with app.app_context():
            self._setup_confirmed_groups(cl_comp)
            result, error = advance_cl_knockout(cl_comp["comp_id"])
            assert error is None
            assert len(set(result["qualified_team_ids"])) == 8


# ── CL Knockout Bracket Tests ────────────────────────────────────────────────

class TestCLKnockoutBracket:
    def test_full_bracket_13_matches(self, app, cl_comp):
        """QF: 4 ties × 2 legs = 8, SF: 2 ties × 2 legs = 4, Final: 1 = 13."""
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            result, error = generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )
            assert error is None
            assert len(result) == 13

    def test_qf_has_actual_teams(self, app, cl_comp):
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            result, error = generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )
            assert error is None
            qf_matches = [m for m in result if m.stage == MatchStage.QUARTER_FINAL]
            assert len(qf_matches) == 8
            for m in qf_matches:
                assert m.home_team_id is not None
                assert m.away_team_id is not None

    def test_sf_and_final_are_placeholders(self, app, cl_comp):
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            result, error = generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )
            assert error is None
            sf_matches = [m for m in result if m.stage == MatchStage.SEMI_FINAL]
            final_matches = [m for m in result if m.stage == MatchStage.FINAL]
            assert len(sf_matches) == 4
            assert len(final_matches) == 1
            for m in sf_matches + final_matches:
                assert m.home_team_id is None
                assert m.away_team_id is None

    def test_bracket_positions_correct(self, app, cl_comp):
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )
            # Final at position 1
            final = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                bracket_position=1,
            ).all()
            assert len(final) == 1

            # SF at positions 2, 3
            sf = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                stage=MatchStage.SEMI_FINAL,
            ).all()
            sf_positions = {m.bracket_position for m in sf}
            assert sf_positions == {2, 3}

            # QF at positions 4-7
            qf = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                stage=MatchStage.QUARTER_FINAL,
            ).all()
            qf_positions = {m.bracket_position for m in qf}
            assert qf_positions == {4, 5, 6, 7}

    def test_rejects_duplicate(self, app, cl_comp):
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )
            result, error = generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )
            assert result is None
            assert "already" in error.lower()


# ── Cup Full Bracket Tests ───────────────────────────────────────────────────

class TestCupBracket:
    def test_8_teams_full_bracket(self, app, cup_comp, base_data):
        """8 teams: 4 R1 matches + 2 QF + 1 SF... actually for 8 teams:
        bracket_size=8, 3 rounds, 7 total matches."""
        with app.app_context():
            _add_cup_teams(8, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            result, error = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            assert error is None
            assert result["num_byes"] == 0
            assert result["total_rounds"] == 3
            # 7 total matches: 4 R1 + 2 inner + 1 final
            assert len(result["matches"]) == 7

    def test_32_teams_full_bracket(self, app, cup_comp, base_data):
        """32 teams: bracket_size=32, 5 rounds, 31 total matches."""
        with app.app_context():
            _add_cup_teams(32, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            result, error = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            assert error is None
            assert result["num_byes"] == 0
            assert result["total_rounds"] == 5
            assert len(result["matches"]) == 31

    def test_48_teams_byes(self, app, cup_comp, base_data):
        """48 teams: bracket_size=64, 16 byes, 47 total matches."""
        with app.app_context():
            _add_cup_teams(48, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            result, error = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            assert error is None
            assert result["num_byes"] == 16
            assert len(result["bye_team_ids"]) == 16
            assert result["total_rounds"] == 6
            # 48-1 = 47 total matches (but 16 leaf matches are skipped as byes)
            # Inner matches: 31 (pos 1-31) + R1 matches: 16 = 47
            assert len(result["matches"]) == 47

    def test_16_teams_round1_matches(self, app, cup_comp, base_data):
        with app.app_context():
            _add_cup_teams(16, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            result, error = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            assert error is None
            assert len(result["round1_matches"]) == 8
            for m in result["round1_matches"]:
                assert m.stage == MatchStage.ROUND_1
                assert m.home_team_id is not None
                assert m.away_team_id is not None

    def test_bracket_has_final_at_position_1(self, app, cup_comp, base_data):
        with app.app_context():
            _add_cup_teams(8, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            final = Match.query.filter_by(
                competition_id=cup_comp["comp_id"],
                bracket_position=1,
            ).first()
            assert final is not None
            assert final.stage == MatchStage.FINAL

    def test_byes_prefill_round2(self, app, cup_comp, base_data):
        """With 48 teams (16 byes), bye teams should be pre-filled into R2 parent slots."""
        with app.app_context():
            _add_cup_teams(48, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            result, error = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            assert error is None
            bye_ids = set(result["bye_team_ids"])

            # Find round 2 matches (inner matches at depth that would be round 2)
            # For bracket_size=64, leaf_start=32, round 2 = positions 16-31
            r2_matches = Match.query.filter_by(
                competition_id=cup_comp["comp_id"],
            ).filter(
                Match.bracket_position >= 16,
                Match.bracket_position <= 31,
            ).all()

            # Some of these should have a bye team pre-filled
            prefilled_teams = set()
            for m in r2_matches:
                if m.home_team_id:
                    prefilled_teams.add(m.home_team_id)
                if m.away_team_id:
                    prefilled_teams.add(m.away_team_id)

            # All bye teams should appear in prefilled
            assert bye_ids.issubset(prefilled_teams)

    def test_rejects_wrong_type(self, app, base_data):
        with app.app_context():
            comp = Competition(
                name="Regional", type=CompetitionType.REGIONAL,
                category=CompetitionCategory.MEN, season_id=base_data["season_id"],
            )
            db.session.add(comp)
            db.session.commit()
            result, error = generate_cup_draw(comp.id, date(2026, 6, 1))
            assert result is None
            assert "cup" in error.lower()

    def test_rejects_duplicate(self, app, cup_comp, base_data):
        with app.app_context():
            _add_cup_teams(8, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            result, error = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            assert result is None
            assert "already" in error.lower()


# ── Bracket Auto-Progression Tests ───────────────────────────────────────────

class TestBracketProgression:
    def test_cup_winner_advances_to_parent(self, app, cup_comp, base_data):
        """When a cup R1 match is confirmed, winner fills parent bracket slot."""
        with app.app_context():
            _add_cup_teams(8, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            result, _ = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))

            # Pick a R1 match and confirm it
            r1_match = result["round1_matches"][0]
            r1_bp = r1_match.bracket_position
            parent_bp = r1_bp // 2
            is_home = (r1_bp % 2 == 0)

            r1_match.home_score = 3
            r1_match.away_score = 1
            r1_match.status = MatchStatus.CONFIRMED
            db.session.commit()

            advance_bracket_winner(r1_match)

            parent = Match.query.filter_by(
                competition_id=cup_comp["comp_id"],
                bracket_position=parent_bp,
            ).first()

            winner_id = r1_match.home_team_id  # home won
            if is_home:
                assert parent.home_team_id == winner_id
            else:
                assert parent.away_team_id == winner_id

    def test_full_cup_progression_to_final(self, app, cup_comp, base_data, admin_id):
        """Confirm all matches through the bracket, verify final teams are filled."""
        with app.app_context():
            team_ids = _add_cup_teams(4, cup_comp["comp_id"],
                                      base_data["region_id"], base_data["county_id"])
            result, _ = generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))

            # 4 teams: bracket_size=4, 2 R1 matches + 1 Final = 3 matches
            assert len(result["matches"]) == 3

            # Confirm R1 matches (home team always wins) using confirm_result
            r1_matches = [m for m in result["matches"] if m.stage == MatchStage.ROUND_1]
            assert len(r1_matches) == 2

            for m in r1_matches:
                m.home_score = 2
                m.away_score = 0
                m.status = MatchStatus.COMPLETED
                db.session.commit()
                confirm_result(m.id, admin_id)

            # Check final has both teams filled
            final = Match.query.filter_by(
                competition_id=cup_comp["comp_id"],
                bracket_position=1,
            ).first()
            assert final.home_team_id is not None
            assert final.away_team_id is not None

    def test_cl_two_legged_progression(self, app, cl_comp, admin_id):
        """Two-legged QF tie: both legs confirmed → winner fills SF slot."""
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )

            # Get QF tie at bracket_position=4 (both legs)
            qf_legs = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                bracket_position=4,
            ).order_by(Match.leg).all()
            assert len(qf_legs) == 2
            leg1, leg2 = qf_legs

            # Leg 1: team A wins 3-1
            leg1.home_score, leg1.away_score = 3, 1
            leg1.status = MatchStatus.COMPLETED
            db.session.commit()
            confirm_result(leg1.id, admin_id)

            # After leg 1 only, SF should still be empty
            parent_bp = 4 // 2  # = 2
            sf_leg1 = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                bracket_position=parent_bp,
                leg=1,
            ).first()
            assert sf_leg1.home_team_id is None  # not yet decided

            # Leg 2: team B wins 2-1 (aggregate: A=4, B=3 → A advances)
            leg2.home_score, leg2.away_score = 2, 1
            leg2.status = MatchStatus.COMPLETED
            db.session.commit()
            confirm_result(leg2.id, admin_id)

            # Now SF should have team A filled
            db.session.refresh(sf_leg1)
            sf_leg2 = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                bracket_position=parent_bp,
                leg=2,
            ).first()

            winner_id = tids[0]  # team A (leg1 home)
            # bp=4 is even → home slot in parent
            assert sf_leg1.home_team_id == winner_id
            assert sf_leg2.away_team_id == winner_id

    def test_away_goals_rule(self, app, cl_comp, admin_id):
        """Tied on aggregate → away goals rule decides."""
        with app.app_context():
            tids = cl_comp["team_ids"]
            pairs = [(tids[0], tids[1]), (tids[2], tids[3]),
                     (tids[4], tids[5]), (tids[6], tids[7])]
            generate_cl_knockout_bracket(
                cl_comp["comp_id"], pairs, date(2026, 9, 1)
            )

            qf_legs = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                bracket_position=4,
            ).order_by(Match.leg).all()
            leg1, leg2 = qf_legs

            # Leg 1: team A 2-1 team B (A home)
            leg1.home_score, leg1.away_score = 2, 1
            leg1.status = MatchStatus.COMPLETED
            db.session.commit()
            confirm_result(leg1.id, admin_id)

            # Leg 2: team B 1-0 team A (B home)
            # Aggregate: A=2+0=2, B=1+1=2. Tied!
            # Away goals: A scored 0 away, B scored 1 away → B advances
            leg2.home_score, leg2.away_score = 1, 0
            leg2.status = MatchStatus.COMPLETED
            db.session.commit()
            confirm_result(leg2.id, admin_id)

            parent_bp = 2  # 4 // 2
            sf_leg1 = Match.query.filter_by(
                competition_id=cl_comp["comp_id"],
                bracket_position=parent_bp,
                leg=1,
            ).first()

            # B wins on away goals, bp=4 is even → home slot
            assert sf_leg1.home_team_id == tids[1]  # team B


# ── Bracket Query Tests ──────────────────────────────────────────────────────

class TestBracketQuery:
    def test_get_bracket_returns_rounds(self, app, cup_comp, base_data):
        with app.app_context():
            _add_cup_teams(8, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
            bracket, error = get_bracket(cup_comp["comp_id"])
            assert error is None
            assert "final" in bracket
            assert "round_1" in bracket

    def test_get_bracket_no_matches(self, app, cup_comp):
        with app.app_context():
            bracket, error = get_bracket(cup_comp["comp_id"])
            assert bracket is None
            assert "no bracket" in error.lower()


# ── API Endpoint Tests ───────────────────────────────────────────────────────

class TestSchedulingAPI:
    def test_generate_fixtures_admin_only(self, app, client, coach_headers,
                                          regional_comp):
        resp = client.post(
            f"/api/competitions/{regional_comp['comp_id']}/generate-fixtures",
            json={"start_date": "2026-01-10"},
            headers=coach_headers,
        )
        assert resp.status_code == 403

    def test_generate_fixtures_success(self, app, client, admin_headers,
                                        regional_comp):
        resp = client.post(
            f"/api/competitions/{regional_comp['comp_id']}/generate-fixtures",
            json={"start_date": "2026-01-10"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["match_count"] == 56

    def test_generate_fixtures_duplicate_409(self, app, client, admin_headers,
                                              regional_comp):
        client.post(
            f"/api/competitions/{regional_comp['comp_id']}/generate-fixtures",
            json={"start_date": "2026-01-10"},
            headers=admin_headers,
        )
        resp = client.post(
            f"/api/competitions/{regional_comp['comp_id']}/generate-fixtures",
            json={"start_date": "2026-01-10"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_matches_filter_by_matchday(self, app, client, admin_headers,
                                         regional_comp):
        client.post(
            f"/api/competitions/{regional_comp['comp_id']}/generate-fixtures",
            json={"start_date": "2026-01-10"},
            headers=admin_headers,
        )
        resp = client.get(
            f"/api/matches?competition_id={regional_comp['comp_id']}&matchday=1"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["matches"]) == 4

    def test_matches_filter_by_stage(self, app, client, admin_headers,
                                      regional_comp):
        client.post(
            f"/api/competitions/{regional_comp['comp_id']}/generate-fixtures",
            json={"start_date": "2026-01-10"},
            headers=admin_headers,
        )
        resp = client.get(
            f"/api/matches?competition_id={regional_comp['comp_id']}&stage=league"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["matches"]) == 56

    def test_cup_draw_api(self, app, client, admin_headers, cup_comp, base_data):
        with app.app_context():
            _add_cup_teams(32, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
        resp = client.post(
            f"/api/competitions/{cup_comp['comp_id']}/generate-cup-draw",
            json={"start_date": "2026-06-01"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total_matches"] == 31
        assert data["round1_matches"] == 16
        assert data["num_byes"] == 0
        assert data["total_rounds"] == 5

    def test_bracket_api(self, app, client, cup_comp, base_data):
        with app.app_context():
            _add_cup_teams(8, cup_comp["comp_id"],
                           base_data["region_id"], base_data["county_id"])
            generate_cup_draw(cup_comp["comp_id"], date(2026, 6, 1))
        resp = client.get(f"/api/competitions/{cup_comp['comp_id']}/bracket")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "bracket" in data
        assert "final" in data["bracket"]

    def test_standings_filter_by_group(self, app, client, admin_headers, cl_comp):
        with app.app_context():
            generate_cl_groups(cl_comp["comp_id"], date(2026, 8, 1))

        resp = client.get(
            f"/api/standings?competition_id={cl_comp['comp_id']}"
            f"&season_id={cl_comp['season_id']}&group_name=A"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["standings"]) == 3
