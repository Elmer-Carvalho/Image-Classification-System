"""add sync_status columns (webdav_failures, server_offline, last_health_check)

Revision ID: a3f2b1c4d5e6
Revises:
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f2b1c4d5e6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'sync_status'"
    ))
    if not result.scalar():
        return
    inspector = sa.inspect(conn)
    existing_columns = [c['name'] for c in inspector.get_columns('sync_status')]
    if 'webdav_failures' not in existing_columns:
        op.add_column('sync_status', sa.Column('webdav_failures', sa.Integer(), nullable=False, server_default='0'))
    if 'server_offline' not in existing_columns:
        op.add_column('sync_status', sa.Column('server_offline', sa.Boolean(), nullable=False, server_default='0'))
    if 'last_health_check' not in existing_columns:
        op.add_column('sync_status', sa.Column('last_health_check', sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c['name'] for c in inspector.get_columns('sync_status')]
    if 'last_health_check' in existing_columns:
        op.drop_column('sync_status', 'last_health_check')
    if 'server_offline' in existing_columns:
        op.drop_column('sync_status', 'server_offline')
    if 'webdav_failures' in existing_columns:
        op.drop_column('sync_status', 'webdav_failures')
