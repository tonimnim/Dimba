import random
from datetime import date

import click
from flask.cli import AppGroup
from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.team import Team, TeamCategory, TeamStatus
from app.models.user import User, UserRole
from app.models.player import Player, PlayerPosition
from app.seeds.data import (
    REGIONS_AND_COUNTIES,
    DEFAULT_ADMIN,
    TEAMS,
    COUNTY_ADMINS,
    COACHES,
    FIRST_NAMES,
    LAST_NAMES,
)

from app.models.match import Match, MatchStatus, MatchStage
from app.models.competition import Competition, CompetitionType, CompetitionCategory
from app.models.season import Season
from app.services.match_service import submit_result, confirm_result

seed_cli = AppGroup("seed", help="Seed database commands.")


@seed_cli.command("regions")
def seed_regions():
    """Seed regions and counties."""
    for region_name, data in REGIONS_AND_COUNTIES.items():
        region = Region.query.filter_by(code=data["code"]).first()
        if not region:
            region = Region(name=region_name, code=data["code"])
            db.session.add(region)
            db.session.flush()

        for county_code, county_name in data["counties"]:
            county = County.query.filter_by(code=county_code).first()
            if not county:
                county = County(
                    name=county_name, code=county_code, region_id=region.id
                )
                db.session.add(county)

    db.session.commit()
    click.echo("Seeded 6 regions and 44 counties.")


@seed_cli.command("admin")
def seed_admin():
    """Seed default super admin user."""
    user = User.query.filter_by(email=DEFAULT_ADMIN["email"]).first()
    if not user:
        user = User(
            email=DEFAULT_ADMIN["email"],
            first_name=DEFAULT_ADMIN["first_name"],
            last_name=DEFAULT_ADMIN["last_name"],
            role=UserRole.SUPER_ADMIN,
        )
        user.set_password(DEFAULT_ADMIN["password"])
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created admin user: {DEFAULT_ADMIN['email']}")
    else:
        click.echo("Admin user already exists.")


@seed_cli.command("all")
def seed_all():
    """Seed all data."""
    # Seed regions and counties
    for region_name, data in REGIONS_AND_COUNTIES.items():
        region = Region.query.filter_by(code=data["code"]).first()
        if not region:
            region = Region(name=region_name, code=data["code"])
            db.session.add(region)
            db.session.flush()

        for county_code, county_name in data["counties"]:
            county = County.query.filter_by(code=county_code).first()
            if not county:
                county = County(
                    name=county_name, code=county_code, region_id=region.id
                )
                db.session.add(county)

    db.session.commit()
    click.echo("Seeded 6 regions and 44 counties.")

    # Seed admin
    user = User.query.filter_by(email=DEFAULT_ADMIN["email"]).first()
    if not user:
        user = User(
            email=DEFAULT_ADMIN["email"],
            first_name=DEFAULT_ADMIN["first_name"],
            last_name=DEFAULT_ADMIN["last_name"],
            role=UserRole.SUPER_ADMIN,
        )
        user.set_password(DEFAULT_ADMIN["password"])
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created admin user: {DEFAULT_ADMIN['email']}")
    else:
        click.echo("Admin user already exists.")

    click.echo("All seed data loaded successfully!")


def _slugify(name):
    """Convert name to a slug for email addresses."""
    return (
        name.lower()
        .replace("'", "")
        .replace(" ", "")
        .replace("-", "")
    )


def _random_dob(rng):
    """Generate a random date of birth for a player aged 18–32."""
    year = 2026 - rng.randint(18, 32)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)  # safe for all months
    return date(year, month, day)


@seed_cli.command("test-data")
def seed_test_data():
    """Seed realistic test data: teams, county admins, coaches, players."""
    rng = random.Random(42)  # deterministic for reproducibility

    # 1. Verify regions and counties exist
    region_count = Region.query.count()
    county_count = County.query.count()
    if region_count == 0 or county_count == 0:
        click.echo("Error: regions and counties must be seeded first. Run: flask seed regions")
        raise SystemExit(1)

    # Build lookup maps
    regions_by_name = {r.name: r for r in Region.query.all()}
    counties_by_name = {c.name: c for c in County.query.all()}

    # 2. Create teams (470 with generated data, 10 per county)
    team_objects = {}
    teams_created = 0
    for region_name, team_name, county_name in TEAMS:
        if Team.query.filter_by(name=team_name).first():
            team_objects[team_name] = Team.query.filter_by(name=team_name).first()
            continue
        region = regions_by_name[region_name]
        county = counties_by_name[county_name]
        team = Team(
            name=team_name,
            county_id=county.id,
            region_id=region.id,
            category=TeamCategory.MEN,
            status=TeamStatus.ACTIVE,
        )
        db.session.add(team)
        team_objects[team_name] = team
        teams_created += 1
    db.session.flush()  # get team IDs

    # 3. Create 44 county admin users
    admins_created = 0
    for county_name, (first, last) in COUNTY_ADMINS.items():
        slug = _slugify(county_name)
        email = f"admin.{slug}@dimba.co.ke"
        if User.query.filter_by(email=email).first():
            continue
        county = counties_by_name.get(county_name)
        if not county:
            continue
        user = User(
            email=email,
            first_name=first,
            last_name=last,
            role=UserRole.COUNTY_ADMIN,
            county_id=county.id,
        )
        user.set_password("County@2026")
        db.session.add(user)
        admins_created += 1

    # 4. Create coach users (one per team, linked to teams)
    coaches_created = 0
    for team_name, (first, last) in COACHES.items():
        slug = _slugify(team_name)
        email = f"coach.{slug}@dimba.co.ke"
        if User.query.filter_by(email=email).first():
            continue
        team = team_objects[team_name]
        user = User(
            email=email,
            first_name=first,
            last_name=last,
            role=UserRole.COACH,
            team_id=team.id,
        )
        user.set_password("Coach@2026")
        db.session.add(user)
        coaches_created += 1

    # 5. Create players (15 per team)
    # Position distribution per team: 2 GK, 5 DEF, 4 MID, 4 FWD
    positions = (
        [PlayerPosition.GK] * 2
        + [PlayerPosition.DEF] * 5
        + [PlayerPosition.MID] * 4
        + [PlayerPosition.FWD] * 4
    )
    players_created = 0
    for team_name, team in team_objects.items():
        existing_count = Player.query.filter_by(team_id=team.id).count()
        if existing_count >= 15:
            continue
        for jersey in range(1, 16):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            player = Player(
                first_name=first,
                last_name=last,
                date_of_birth=_random_dob(rng),
                position=positions[jersey - 1],
                jersey_number=jersey,
                team_id=team.id,
            )
            db.session.add(player)
            players_created += 1

    # 6. Commit
    db.session.commit()

    # 7. Summary
    click.echo(
        f"Created {teams_created} teams, {admins_created} county admins, "
        f"{coaches_created} coaches, {players_created} players"
    )


@seed_cli.command("simulate-results")
def seed_simulate_results():
    """[TEMP] Submit and confirm random scores for all scheduled league matches."""
    rng = random.Random(42)

    # Find admin user to act as submitter/confirmer
    admin = User.query.filter_by(role=UserRole.SUPER_ADMIN).first()
    if not admin:
        click.echo("Error: no admin user found. Run: flask seed admin")
        raise SystemExit(1)

    matches = (
        Match.query
        .filter_by(stage=MatchStage.LEAGUE, status=MatchStatus.SCHEDULED)
        .order_by(Match.match_date, Match.id)
        .all()
    )

    if not matches:
        click.echo("No scheduled league matches found.")
        return

    submitted = 0
    confirmed = 0
    errors = []

    for match in matches:
        home_score = rng.randint(0, 5)
        away_score = rng.randint(0, 5)

        # Submit
        _, err = submit_result(match.id, home_score, away_score, admin.id)
        if err:
            errors.append(f"Match {match.id} submit: {err}")
            continue
        submitted += 1

        # Confirm
        _, err = confirm_result(match.id, admin.id)
        if err:
            errors.append(f"Match {match.id} confirm: {err}")
            continue
        confirmed += 1

    click.echo(f"Submitted: {submitted}, Confirmed: {confirmed}")
    if errors:
        click.echo(f"Errors ({len(errors)}):")
        for e in errors:
            click.echo(f"  - {e}")


@seed_cli.command("county-competitions")
def seed_county_competitions():
    """Create one county competition per county for the active season, and assign teams."""
    season = Season.query.order_by(Season.year.desc()).first()
    if not season:
        click.echo("Error: no season found. Create a season first.")
        raise SystemExit(1)

    counties = County.query.all()
    created = 0
    for county in counties:
        name = f"{county.name} County League {season.year}"
        existing = Competition.query.filter_by(name=name, season_id=season.id).first()
        if existing:
            continue

        comp = Competition(
            name=name,
            type=CompetitionType.COUNTY,
            category=CompetitionCategory.MEN,
            season_id=season.id,
            region_id=county.region_id,
            county_id=county.id,
        )
        db.session.add(comp)
        db.session.flush()

        # Add all teams from this county
        teams = Team.query.filter_by(county_id=county.id).all()
        for team in teams:
            comp.teams.append(team)

        created += 1

    db.session.commit()
    click.echo(f"Created {created} county competitions for season {season.year}")


@seed_cli.command("regional-competitions")
def seed_regional_competitions():
    """Create one regional competition per region for the active season (no teams yet)."""
    season = Season.query.order_by(Season.year.desc()).first()
    if not season:
        click.echo("Error: no season found. Create a season first.")
        raise SystemExit(1)

    regions = Region.query.all()
    created = 0
    for region in regions:
        name = f"{region.name} Regional League {season.year}"
        existing = Competition.query.filter_by(name=name, season_id=season.id).first()
        if existing:
            continue

        comp = Competition(
            name=name,
            type=CompetitionType.REGIONAL,
            category=CompetitionCategory.MEN,
            season_id=season.id,
            region_id=region.id,
        )
        db.session.add(comp)
        created += 1

    db.session.commit()
    click.echo(f"Created {created} regional competitions for season {season.year}")


@seed_cli.command("full-season")
@click.pass_context
def seed_full_season(ctx):
    """Seed a complete season: regions -> admin -> test-data -> county competitions -> regional competitions."""
    ctx.invoke(seed_regions)
    ctx.invoke(seed_admin)
    ctx.invoke(seed_test_data)
    ctx.invoke(seed_county_competitions)
    ctx.invoke(seed_regional_competitions)
    click.echo("Full season seeded successfully!")
