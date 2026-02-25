"""add_multipla_escolha

Revision ID: e7efd594e4cd
Revises: b4e5c6d7e8f9
Create Date: 2026-02-25 04:00:08.277805

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7efd594e4cd'
down_revision: Union[str, None] = 'b4e5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cria a coluna no banco de dados de produção
    op.add_column('ambientes', sa.Column('multipla_escolha', sa.Boolean(), server_default='false', nullable=True))

def downgrade() -> None:
    # Remove a coluna caso precise reverter
    op.drop_column('ambientes', 'multipla_escolha')
