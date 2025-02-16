"""add container type

Revision ID: xxxx
Revises: previous_revision
Create Date: 2024-02-18 22:43:08.599

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add container_type column
    op.add_column('containers', sa.Column('container_type', sa.String()))

def downgrade():
    # Remove container_type column
    op.drop_column('containers', 'container_type') 