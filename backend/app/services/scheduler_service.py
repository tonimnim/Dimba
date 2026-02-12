import math
import random
from datetime import timedelta

from app.extensions import db
from app.models.competition import Competition, CompetitionType
from app.models.match import Match, MatchStage, MatchStatus
from app.models.standing import Standing
from app.services.standings import sort_standings


# ── Round-Robin (Regional) ───────────────────────────────────────────────────

def generate_round_robin(competition_id, start_date, interval_days=7):
    """Generate a full home-and-away round-robin schedule for a regional competition.

    For n teams: (n-1) rounds × 2 passes = 2(n-1) matchdays, n/2 matches per matchday.
    8 teams → 14 matchdays, 56 matches total.

    Rounds are ordered so that matchdays with more intra-county matches come first.
    This minimises early-season travel costs — local derbies are played first,
    cross-county matches are scheduled later as the season progresses.
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    if competition.type != CompetitionType.REGIONAL:
        return None, "Round-robin is only for regional competitions"

    teams = list(competition.teams)
    if len(teams) < 2:
        return None, "Competition must have at least 2 teams"

    existing = Match.query.filter_by(
        competition_id=competition_id, stage=MatchStage.LEAGUE
    ).first()
    if existing:
        return None, "Fixtures already generated for this competition"

    n = len(teams)
    if n % 2 != 0:
        teams.append(None)
        n += 1

    half = n // 2
    rounds = []
    rotating = list(range(1, n))

    for r in range(n - 1):
        round_pairs = []
        round_pairs.append((0, rotating[0]))
        for i in range(1, half):
            round_pairs.append((rotating[i], rotating[n - 1 - i]))
        rounds.append(round_pairs)
        rotating = [rotating[-1]] + rotating[:-1]

    # Sort rounds so that matchdays with more same-county matches come first.
    # This ensures local derbies are played early and cross-county travel later.
    def _county_score(round_pairs):
        score = 0
        for home_idx, away_idx in round_pairs:
            home = teams[home_idx]
            away = teams[away_idx]
            if home is not None and away is not None and home.county_id == away.county_id:
                score += 1
        return score

    rounds.sort(key=_county_score, reverse=True)

    matches = []
    matchday = 0

    # First pass: original home/away
    for round_pairs in rounds:
        matchday += 1
        match_date = start_date + timedelta(days=(matchday - 1) * interval_days)
        for home_idx, away_idx in round_pairs:
            home = teams[home_idx]
            away = teams[away_idx]
            if home is None or away is None:
                continue
            match = Match(
                competition_id=competition_id,
                season_id=competition.season_id,
                home_team_id=home.id,
                away_team_id=away.id,
                match_date=match_date,
                stage=MatchStage.LEAGUE,
                matchday=matchday,
                status=MatchStatus.SCHEDULED,
            )
            db.session.add(match)
            matches.append(match)

    # Second pass: reversed home/away (same round order so local derbies stay early)
    for round_pairs in rounds:
        matchday += 1
        match_date = start_date + timedelta(days=(matchday - 1) * interval_days)
        for home_idx, away_idx in round_pairs:
            home = teams[home_idx]
            away = teams[away_idx]
            if home is None or away is None:
                continue
            match = Match(
                competition_id=competition_id,
                season_id=competition.season_id,
                home_team_id=away.id,
                away_team_id=home.id,
                match_date=match_date,
                stage=MatchStage.LEAGUE,
                matchday=matchday,
                status=MatchStatus.SCHEDULED,
            )
            db.session.add(match)
            matches.append(match)

    actual_teams = [t for t in teams if t is not None]
    for team in actual_teams:
        standing = Standing(
            team_id=team.id,
            competition_id=competition_id,
            season_id=competition.season_id,
        )
        db.session.add(standing)

    db.session.commit()
    return matches, None


# ── Champions League Groups ──────────────────────────────────────────────────

def generate_cl_groups(competition_id, start_date, interval_days=7):
    """Generate Champions League group stage: 21 teams into 7 groups of 3.

    Constraint: no two teams from the same region in one group.
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    if competition.type != CompetitionType.NATIONAL:
        return None, "Group draw is only for national (Champions League) competitions"

    teams = list(competition.teams)
    if len(teams) != 21:
        return None, "Champions League requires exactly 21 teams"

    existing = Match.query.filter_by(
        competition_id=competition_id, stage=MatchStage.GROUP
    ).first()
    if existing:
        return None, "Group fixtures already generated for this competition"

    region_map = {}
    for team in teams:
        region_map.setdefault(team.region_id, []).append(team)

    if len(region_map) != 7:
        return None, "Champions League requires teams from exactly 7 regions"

    for region_id, region_teams in region_map.items():
        if len(region_teams) != 3:
            return None, "Each region must contribute exactly 3 teams"

    region_ids = list(region_map.keys())
    random.shuffle(region_ids)
    for rid in region_ids:
        random.shuffle(region_map[rid])

    group_letters = ["A", "B", "C", "D", "E", "F", "G"]
    groups = {letter: [] for letter in group_letters}

    # Pot-based assignment: pot 0 (offset 0), pot 1 (offset +2), pot 2 (offset +4)
    # With 7 regions and 7 groups, each pot has 7 teams, one per region.
    # Offsets of 0, 2, 4 guarantee no two teams from the same region share a group.
    for i, rid in enumerate(region_ids):
        for j, team in enumerate(region_map[rid]):
            group_idx = (i + j * 2) % 7
            groups[group_letters[group_idx]].append(team)

    for letter, group_teams in groups.items():
        region_ids_in_group = [t.region_id for t in group_teams]
        if len(set(region_ids_in_group)) != len(region_ids_in_group):
            return None, "Group draw failed: same-region teams in one group"

    matches = []
    for letter, group_teams in groups.items():
        a, b, c = group_teams
        pairings = [
            (a, b, 1), (c, a, 2), (b, c, 3),
            (b, a, 4), (a, c, 5), (c, b, 6),
        ]
        for home, away, md in pairings:
            match_date = start_date + timedelta(days=(md - 1) * interval_days)
            match = Match(
                competition_id=competition_id,
                season_id=competition.season_id,
                home_team_id=home.id,
                away_team_id=away.id,
                match_date=match_date,
                stage=MatchStage.GROUP,
                group_name=letter,
                matchday=md,
                status=MatchStatus.SCHEDULED,
            )
            db.session.add(match)
            matches.append(match)

        for team in group_teams:
            standing = Standing(
                team_id=team.id,
                competition_id=competition_id,
                season_id=competition.season_id,
                group_name=letter,
            )
            db.session.add(standing)

    db.session.commit()

    return {
        "groups": {letter: [t.id for t in gteams] for letter, gteams in groups.items()},
        "matches": matches,
    }, None


# ── CL Knockout Advancement ─────────────────────────────────────────────────

def advance_cl_knockout(competition_id):
    """Determine 8 teams for CL quarter-finals from group standings.

    7 group winners + 1 best runner-up.
    Returns qualified teams and QF pairings.
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    if competition.type != CompetitionType.NATIONAL:
        return None, "Knockout advancement is only for national competitions"

    group_letters = ["A", "B", "C", "D", "E", "F", "G"]
    winners = []
    runners_up = []

    for letter in group_letters:
        raw = Standing.query.filter_by(
            competition_id=competition_id,
            season_id=competition.season_id,
            group_name=letter,
        ).all()
        standings = sort_standings(raw, competition_id, competition.season_id)
        if len(standings) < 2:
            return None, f"Group {letter} does not have enough teams with standings"

        winners.append(standings[0])
        runners_up.append(standings[1])

    runners_up.sort(
        key=lambda s: (s.points, s.goal_difference, s.goals_for), reverse=True
    )
    best_runners = runners_up[:1]

    qualified_team_ids = [s.team_id for s in winners] + [s.team_id for s in best_runners]

    winners.sort(key=lambda s: (s.points, s.goal_difference, s.goals_for), reverse=True)

    seeded = [s.team_id for s in winners[:4]]
    unseeded = [s.team_id for s in winners[4:]] + [s.team_id for s in best_runners]

    winner_groups = {s.team_id: s.group_name for s in winners}
    runner_groups = {s.team_id: s.group_name for s in best_runners}
    all_groups = {**winner_groups, **runner_groups}

    random.shuffle(unseeded)
    pairs = []
    used = set()

    for s_id in seeded:
        for u_id in unseeded:
            if u_id not in used and all_groups.get(s_id) != all_groups.get(u_id):
                pairs.append((s_id, u_id))
                used.add(u_id)
                break
        else:
            for u_id in unseeded:
                if u_id not in used:
                    pairs.append((s_id, u_id))
                    used.add(u_id)
                    break

    return {
        "qualified_team_ids": qualified_team_ids,
        "pairings": pairs,
    }, None


# ── Full Knockout Bracket (CL) ──────────────────────────────────────────────

def generate_cl_knockout_bracket(competition_id, team_pairs, start_date, interval_days=14):
    """Generate the full CL knockout bracket: QF → SF → Final.

    Uses bracket_position (binary heap): 1=Final, 2-3=SF, 4-7=QF.
    QF and SF are two-legged; Final is single-leg.
    QF matches have actual teams; SF and Final are placeholders (null teams)
    that auto-fill as results are confirmed.
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    if competition.type != CompetitionType.NATIONAL:
        return None, "Knockout bracket is only for national competitions"

    if len(team_pairs) != 4:
        return None, "Quarter-finals require exactly 4 pairings"

    existing = Match.query.filter_by(
        competition_id=competition_id, stage=MatchStage.QUARTER_FINAL
    ).first()
    if existing:
        return None, "Knockout bracket already generated for this competition"

    matches = []
    season_id = competition.season_id
    round_offset = 0

    # ── Final (bracket_position=1, single leg) ───────────────────────
    final_date = start_date + timedelta(days=interval_days * 4)
    final = Match(
        competition_id=competition_id,
        season_id=season_id,
        home_team_id=None,
        away_team_id=None,
        match_date=final_date,
        stage=MatchStage.FINAL,
        bracket_position=1,
        round_number=_stage_to_round_number(MatchStage.FINAL),
        status=MatchStatus.SCHEDULED,
    )
    db.session.add(final)
    matches.append(final)

    # ── Semi-Finals (bracket_position=2,3, two-legged) ───────────────
    for bp in [2, 3]:
        sf_date = start_date + timedelta(days=interval_days * 2)
        for leg in [1, 2]:
            m = Match(
                competition_id=competition_id,
                season_id=season_id,
                home_team_id=None,
                away_team_id=None,
                match_date=sf_date + timedelta(days=(leg - 1) * 7),
                stage=MatchStage.SEMI_FINAL,
                bracket_position=bp,
                leg=leg,
                round_number=_stage_to_round_number(MatchStage.SEMI_FINAL),
                status=MatchStatus.SCHEDULED,
            )
            db.session.add(m)
            matches.append(m)

    # ── Quarter-Finals (bracket_position=4-7, two-legged, actual teams) ──
    for i, (team_a_id, team_b_id) in enumerate(team_pairs):
        bp = 4 + i
        for leg in [1, 2]:
            if leg == 1:
                home_id, away_id = team_a_id, team_b_id
            else:
                home_id, away_id = team_b_id, team_a_id
            m = Match(
                competition_id=competition_id,
                season_id=season_id,
                home_team_id=home_id,
                away_team_id=away_id,
                match_date=start_date + timedelta(days=(leg - 1) * 7),
                stage=MatchStage.QUARTER_FINAL,
                bracket_position=bp,
                leg=leg,
                round_number=_stage_to_round_number(MatchStage.QUARTER_FINAL),
                status=MatchStatus.SCHEDULED,
            )
            db.session.add(m)
            matches.append(m)

    db.session.commit()
    return matches, None


# ── Full Cup Bracket ─────────────────────────────────────────────────────────

def generate_cup_draw(competition_id, start_date, interval_days=7):
    """Generate the full cup bracket from Round 1 to Final.

    Uses bracket_position (binary heap): 1=Final, 2-3=SF, 4-7=QF, etc.
    Leaf matches have actual teams; inner matches are placeholders.
    Bye teams are pre-filled into their parent slots.
    All single-leg (no two-legged ties in cup).

    For n teams: total matches = n-1 (single elimination).
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    if competition.type != CompetitionType.CUP:
        return None, "Cup draw is only for cup competitions"

    teams = list(competition.teams)
    if len(teams) < 2:
        return None, "Competition must have at least 2 teams"

    existing = Match.query.filter_by(
        competition_id=competition_id,
    ).filter(Match.bracket_position.isnot(None)).first()
    if existing:
        return None, "Cup bracket already generated for this competition"

    n = len(teams)
    bracket_size = _next_power_of_2(n)
    num_rounds = int(math.log2(bracket_size))
    num_byes = bracket_size - n
    leaf_start = bracket_size // 2  # first leaf bracket_position

    random.shuffle(teams)

    # Split into bye teams and playing teams
    bye_teams = teams[:num_byes]
    playing_teams = teams[num_byes:]

    # Create ALL inner bracket matches (pos 1 to leaf_start-1) as placeholders
    matches = []
    season_id = competition.season_id
    bp_to_match = {}

    for bp in range(1, leaf_start):
        stage = _bracket_pos_to_stage(bp, num_rounds)
        depth = int(math.log2(bp))
        round_num = num_rounds - depth
        match_date = start_date + timedelta(days=(round_num - 1) * interval_days)

        m = Match(
            competition_id=competition_id,
            season_id=season_id,
            home_team_id=None,
            away_team_id=None,
            match_date=match_date,
            stage=stage,
            bracket_position=bp,
            round_number=round_num,
            status=MatchStatus.SCHEDULED,
        )
        db.session.add(m)
        matches.append(m)
        bp_to_match[bp] = m

    # Assign leaf positions: first num_byes get bye teams, rest get actual matches
    # Each leaf position (leaf_start to bracket_size-1) is one matchup
    bye_team_ids = []
    round1_matches = []

    # Bye leaves: each bye team advances directly to parent
    for i in range(num_byes):
        bp = leaf_start + i
        parent_bp = bp // 2
        is_home = (bp % 2 == 0)

        bye_team_ids.append(bye_teams[i].id)
        if parent_bp in bp_to_match:
            parent = bp_to_match[parent_bp]
            if is_home:
                parent.home_team_id = bye_teams[i].id
            else:
                parent.away_team_id = bye_teams[i].id

    # Playing leaves: pair up remaining teams into actual matches
    match_idx = 0
    for i in range(num_byes, leaf_start):
        bp = leaf_start + i
        team_a = playing_teams[match_idx * 2]
        team_b = playing_teams[match_idx * 2 + 1]
        match_idx += 1

        m = Match(
            competition_id=competition_id,
            season_id=season_id,
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            match_date=start_date,
            stage=MatchStage.ROUND_1,
            bracket_position=bp,
            round_number=1,
            status=MatchStatus.SCHEDULED,
        )
        db.session.add(m)
        matches.append(m)
        round1_matches.append(m)
        bp_to_match[bp] = m

    db.session.commit()

    return {
        "matches": matches,
        "round1_matches": round1_matches,
        "bye_team_ids": bye_team_ids,
        "num_byes": num_byes,
        "total_rounds": num_rounds,
    }, None


# ── Bracket Progression ─────────────────────────────────────────────────────

def advance_bracket_winner(match):
    """After a match is confirmed, advance the winner to the parent bracket slot.

    For single-leg: winner determined immediately.
    For two-legged: winner determined by aggregate after BOTH legs confirmed.
    Populates parent match team slots. For two-legged parent ties,
    fills both leg 1 and leg 2.
    """
    if match.bracket_position is None or match.bracket_position == 1:
        return  # No bracket or already the final root

    # Determine if this is a two-legged tie
    if match.leg is not None:
        return _advance_two_legged(match)
    else:
        return _advance_single_leg(match)


def _advance_single_leg(match):
    """Single-leg match: winner goes to parent bracket_position."""
    if match.home_score is None or match.away_score is None:
        return

    if match.home_score == match.away_score:
        # Draw — use penalty winner if set
        if match.penalty_winner_id:
            winner_id = match.penalty_winner_id
        else:
            return  # No penalty winner specified, can't advance
    else:
        winner_id = match.home_team_id if match.home_score > match.away_score else match.away_team_id

    parent_bp = match.bracket_position // 2
    is_home = (match.bracket_position % 2 == 0)

    _fill_parent_slot(match.competition_id, parent_bp, winner_id, is_home)


def _advance_two_legged(match):
    """Two-legged tie: check if both legs confirmed, then advance aggregate winner."""
    # Find both legs of this tie
    legs = Match.query.filter_by(
        competition_id=match.competition_id,
        bracket_position=match.bracket_position,
    ).all()

    if len(legs) < 2:
        return

    leg1 = next((m for m in legs if m.leg == 1), None)
    leg2 = next((m for m in legs if m.leg == 2), None)

    if not leg1 or not leg2:
        return

    # Both must be confirmed
    if leg1.status != MatchStatus.CONFIRMED or leg2.status != MatchStatus.CONFIRMED:
        return

    # In a two-legged tie, leg1 home = leg2 away = "team A"
    team_a_id = leg1.home_team_id
    team_b_id = leg1.away_team_id

    # Aggregate score
    team_a_goals = (leg1.home_score or 0) + (leg2.away_score or 0)
    team_b_goals = (leg1.away_score or 0) + (leg2.home_score or 0)

    if team_a_goals > team_b_goals:
        winner_id = team_a_id
    elif team_b_goals > team_a_goals:
        winner_id = team_b_id
    else:
        # Tied on aggregate — use away goals rule
        team_a_away = leg2.away_score or 0  # team A's away goals (scored in leg 2)
        team_b_away = leg1.away_score or 0  # team B's away goals (scored in leg 1)
        if team_a_away > team_b_away:
            winner_id = team_a_id
        elif team_b_away > team_a_away:
            winner_id = team_b_id
        else:
            return  # Still tied — needs manual resolution (penalties etc.)

    parent_bp = match.bracket_position // 2
    is_home = (match.bracket_position % 2 == 0)

    _fill_parent_slot(match.competition_id, parent_bp, winner_id, is_home)


def _fill_parent_slot(competition_id, parent_bp, winner_id, is_home):
    """Fill the winner into the parent bracket match(es).

    For single-leg parent: fill one match.
    For two-legged parent (has leg 1 and 2): fill both legs
    (home in leg 1, away in leg 2 or vice versa).
    """
    parent_matches = Match.query.filter_by(
        competition_id=competition_id,
        bracket_position=parent_bp,
    ).all()

    if not parent_matches:
        return

    # Check if parent is two-legged
    legs = {m.leg for m in parent_matches}

    if legs == {None} or len(parent_matches) == 1:
        # Single-leg parent (e.g., Final)
        parent = parent_matches[0]
        if is_home:
            parent.home_team_id = winner_id
        else:
            parent.away_team_id = winner_id
    else:
        # Two-legged parent: home in leg 1 = away in leg 2
        leg1 = next((m for m in parent_matches if m.leg == 1), None)
        leg2 = next((m for m in parent_matches if m.leg == 2), None)
        if is_home:
            if leg1:
                leg1.home_team_id = winner_id
            if leg2:
                leg2.away_team_id = winner_id
        else:
            if leg1:
                leg1.away_team_id = winner_id
            if leg2:
                leg2.home_team_id = winner_id

    db.session.commit()


# ── Bracket Query ────────────────────────────────────────────────────────────

def get_bracket(competition_id):
    """Return all bracket matches for a competition, organized by round."""
    matches = Match.query.filter_by(
        competition_id=competition_id,
    ).filter(
        Match.bracket_position.isnot(None)
    ).order_by(
        Match.bracket_position, Match.leg
    ).all()

    if not matches:
        return None, "No bracket found for this competition"

    rounds = {}
    for m in matches:
        stage = m.stage.value if m.stage else "unknown"
        rounds.setdefault(stage, []).append({
            "match_id": m.id,
            "bracket_position": m.bracket_position,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "leg": m.leg,
            "status": m.status.value,
            "match_date": m.match_date.isoformat() if m.match_date else None,
        })

    return rounds, None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _next_power_of_2(n):
    """Return the smallest power of 2 >= n."""
    return 1 << (n - 1).bit_length()


def _stage_to_round_number(stage):
    mapping = {
        MatchStage.ROUND_1: 1,
        MatchStage.ROUND_2: 2,
        MatchStage.ROUND_3: 3,
        MatchStage.ROUND_OF_16: 4,
        MatchStage.QUARTER_FINAL: 5,
        MatchStage.SEMI_FINAL: 6,
        MatchStage.FINAL: 7,
    }
    return mapping.get(stage)


def _bracket_pos_to_stage(bp, total_rounds):
    """Map a bracket_position to its MatchStage based on depth in the tree.

    bp=1 → Final, bp=2-3 → SF, bp=4-7 → QF, etc.
    Depth = floor(log2(bp)), round_from_final = depth.
    """
    depth = int(math.log2(bp)) if bp > 0 else 0
    # depth 0 = Final, 1 = SF, 2 = QF, 3 = Ro16, etc.
    stage_map = {
        0: MatchStage.FINAL,
        1: MatchStage.SEMI_FINAL,
        2: MatchStage.QUARTER_FINAL,
        3: MatchStage.ROUND_OF_16,
        4: MatchStage.ROUND_3,
        5: MatchStage.ROUND_2,
    }
    return stage_map.get(depth, MatchStage.ROUND_1)


def _count_to_stage(team_count):
    mapping = {
        32: MatchStage.ROUND_2,
        16: MatchStage.ROUND_OF_16,
        8: MatchStage.QUARTER_FINAL,
        4: MatchStage.SEMI_FINAL,
        2: MatchStage.FINAL,
    }
    return mapping.get(team_count, MatchStage.ROUND_2)
