"""create initial tables

Revision ID: 64663ad0df98
Revises: 
Create Date: 2025-02-16 18:04:16.325160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64663ad0df98'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('containers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=True),
    sa.Column('location', sa.String(length=50), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('start_time', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=True),
    sa.Column('value', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('schedules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scenario_name', sa.String(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=True),
    sa.Column('recurrence_rule', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('devices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_name', sa.String(length=100), nullable=False),
    sa.Column('container_id', sa.Integer(), nullable=True),
    sa.Column('location', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('device_type', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['container_id'], ['containers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sensors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('sensor_type', sa.String(length=100), nullable=True),
    sa.Column('base_value', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=True),
    sa.Column('variation_range', sa.Float(), nullable=True),
    sa.Column('change_rate', sa.Float(), nullable=True),
    sa.Column('interval', sa.Integer(), nullable=True),
    sa.Column('error_definition', sa.Text(), nullable=True),
    sa.Column('device_id', sa.Integer(), nullable=True),
    sa.Column('current_value', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('sensors')
    op.drop_table('devices')
    op.drop_table('schedules')
    op.drop_table('options')
    op.drop_table('containers')
    # ### end Alembic commands ###
