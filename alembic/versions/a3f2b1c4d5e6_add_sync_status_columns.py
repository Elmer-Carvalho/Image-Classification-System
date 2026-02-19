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
    # Tabela sync_status é criada por create_all() antes desta migração.
    # ADD COLUMN IF NOT EXISTS evita erro se a coluna já existir (ex.: create_all já criou com schema atual).
    conn = op.get_bind()
    # Só alterar se a tabela existir (em primeiro deploy create_all pode ainda não ter rodado na ordem esperada)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sync_status')"
    ))
    if not result.scalar():
        return  # Tabela não existe; create_all vai criá-la com schema completo
    conn.execute(sa.text("""
        ALTER TABLE sync_status
        ADD COLUMN IF NOT EXISTS webdav_failures INTEGER NOT NULL DEFAULT 0
    """))
    conn.execute(sa.text("""
        ALTER TABLE sync_status
        ADD COLUMN IF NOT EXISTS server_offline BOOLEAN NOT NULL DEFAULT FALSE
    """))
    conn.execute(sa.text("""
        ALTER TABLE sync_status
        ADD COLUMN IF NOT EXISTS last_health_check TIMESTAMP WITH TIME ZONE
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE sync_status DROP COLUMN IF EXISTS last_health_check"))
    conn.execute(sa.text("ALTER TABLE sync_status DROP COLUMN IF EXISTS server_offline"))
    conn.execute(sa.text("ALTER TABLE sync_status DROP COLUMN IF EXISTS webdav_failures"))
