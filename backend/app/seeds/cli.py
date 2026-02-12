import click
from flask.cli import AppGroup
from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.user import User, UserRole
from app.seeds.data import REGIONS_AND_COUNTIES, DEFAULT_ADMIN

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
