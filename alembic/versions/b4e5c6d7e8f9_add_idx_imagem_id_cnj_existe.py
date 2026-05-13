"""add index idx_imagem_id_cnj_existe on imagens (id_cnj, existe_no_nextcloud)

Revision ID: b4e5c6d7e8f9
Revises: a3f2b1c4d5e6
Create Date: 2026-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4e5c6d7e8f9"
down_revision: Union[str, None] = "a3f2b1c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('imagens')]
    if 'idx_imagem_id_cnj_existe' not in existing_indexes:
        op.create_index('idx_imagem_id_cnj_existe', 'imagens', ['id_cnj', 'existe_no_nextcloud'])


def downgrade() -> None:
    op.drop_index("idx_imagem_id_cnj_existe", table_name="imagens")
