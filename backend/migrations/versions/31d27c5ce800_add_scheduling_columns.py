"""add scheduling columns

Revision ID: 31d27c5ce800
Revises: 6a5fb4f63b1d
Create Date: 2026-02-07 06:52:48.058374

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '31d27c5ce800'
down_revision = '6a5fb4f63b1d'
branch_labels = None
depends_on = None


matchstage_enum = sa.Enum(
    'SUPER', 'LEAGUE', 'GROUP', 'ROUND_1', 'ROUND_2', 'ROUND_3',
    'ROUND_OF_16', 'QUARTER_FINAL', 'SEMI_FINAL', 'FINAL',
    name='matchstage',
)


def upgrade():
    # Create the enum type explicitly for PostgreSQL
    matchstage_enum.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('matchday', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stage', matchstage_enum, nullable=True))
        batch_op.add_column(sa.Column('group_name', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('leg', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('round_number', sa.Integer(), nullable=True))

    with op.batch_alter_table('standings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_name', sa.String(length=10), nullable=True))


def downgrade():
    with op.batch_alter_table('standings', schema=None) as batch_op:
        batch_op.drop_column('group_name')

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_column('round_number')
        batch_op.drop_column('leg')
        batch_op.drop_column('group_name')
        batch_op.drop_column('stage')
        batch_op.drop_column('matchday')

    matchstage_enum.drop(op.get_bind(), checkfirst=True)
