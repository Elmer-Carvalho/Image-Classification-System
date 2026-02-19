"""
Execução programática das migrações Alembic.
Usado no lifespan da aplicação para garantir schema atualizado antes do restante do startup.
"""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def get_alembic_config() -> Config:
    """Retorna configuração do Alembic com path correto para alembic.ini."""
    # Diretório raiz do projeto (onde está alembic.ini)
    # __file__ = app/db/run_migrations.py -> parent.parent = raiz do projeto
    project_root = Path(__file__).resolve().parent.parent.parent
    alembic_ini_path = project_root / "alembic.ini"
    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"alembic.ini não encontrado em {project_root}")
    config = Config(str(alembic_ini_path))
    # Garantir que o script_location é absoluto
    config.set_main_option("script_location", str(project_root / "alembic"))
    return config


def run_upgrade_head() -> None:
    """
    Executa todas as migrações pendentes (alembic upgrade head).
    Bloqueia até concluir. Chamado no startup do lifespan.
    """
    config = get_alembic_config()
    # command.upgrade roda de forma síncrona e bloqueia até terminar
    command.upgrade(config, "head")


def run_stamp_head() -> None:
    """
    Marca o banco como estando na revisão 'head' sem executar migrações.
    Usado em desenvolvimento após create_all (banco recriado já está atualizado).
    """
    config = get_alembic_config()
    command.stamp(config, "head")
