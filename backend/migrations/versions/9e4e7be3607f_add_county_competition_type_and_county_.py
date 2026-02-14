"""add county competition type and county_id

Revision ID: 9e4e7be3607f
Revises: aba2507b3b2c
Create Date: 2026-02-13 23:58:34.292338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e4e7be3607f'
down_revision = 'aba2507b3b2c'
branch_labels = None
depends_on = None


def upgrade():
    # Add new enum values for PostgreSQL
    op.execute("ALTER TYPE competitiontype ADD VALUE IF NOT EXISTS 'SUPER'")
    op.execute("ALTER TYPE competitiontype ADD VALUE IF NOT EXISTS 'COUNTY'")

    with op.batch_alter_table('competitions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('county_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_competitions_county', 'counties', ['county_id'], ['id'])


def downgrade():
    with op.batch_alter_table('competitions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_competitions_county', type_='foreignkey')
        batch_op.drop_column('county_id')

    # Note: PostgreSQL does not support removing enum values
