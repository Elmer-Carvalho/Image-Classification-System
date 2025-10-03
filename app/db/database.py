from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from app.core.config import settings
import time
import logging

logger = logging.getLogger(__name__)

# Create database engine
engine = create_engine(settings.DATABASE_URL)

def wait_for_database(max_retries=30, retry_interval=2):
    """
    Aguarda o banco de dados estar pronto para conexões.
    
    Args:
        max_retries: Número máximo de tentativas
        retry_interval: Intervalo entre tentativas em segundos
    
    Returns:
        bool: True se conectou com sucesso, False caso contrário
    """
    for attempt in range(max_retries):
        try:
            # Tenta conectar ao banco
            with engine.connect() as conn:
                # Executa uma query simples para verificar se está funcionando
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            logger.info("✅ Conexão com banco de dados estabelecida com sucesso!")
            return True
        except OperationalError as e:
            logger.warning(f"⏳ Tentativa {attempt + 1}/{max_retries} - Banco não está pronto: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                logger.error("❌ Falha ao conectar com o banco de dados após todas as tentativas")
                return False
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao conectar com o banco: {e}")
            return False
    
    return False

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# O timezone do banco deve ser configurado para 'America/Sao_Paulo' diretamente no banco PostgreSQL.
# Os modelos ORM usam DateTime(timezone=True) para garantir compatibilidade.
# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Função para popular a tabela de eventos de auditoria
from app.db.models import EventoAuditoria
from sqlalchemy.orm import Session

def popular_eventos_auditoria(db: Session):
    eventos = [
        {"nome": "login", "descricao": "Login de usuário"},
        {"nome": "cadastrar_usuario_convencional", "descricao": "Cadastro de usuário convencional"},
        {"nome": "cadastrar_usuario_administrador", "descricao": "Cadastro de usuário administrador"},
        {"nome": "listar_usuarios", "descricao": "Listagem de usuários"},
        {"nome": "excluir_usuario", "descricao": "Exclusão lógica de usuário"},
        {"nome": "reativar_usuario", "descricao": "Reativação de usuário"},
        {"nome": "cadastrar_email_permitido", "descricao": "Cadastro de e-mail permitido"},
        {"nome": "listar_cadastros_permitidos", "descricao": "Listagem de e-mails permitidos"},
        {"nome": "excluir_cadastro_permitido", "descricao": "Exclusão lógica de e-mail permitido"},
        {"nome": "reativar_cadastro_permitido", "descricao": "Reativação de e-mail permitido"},
        {"nome": "criar_ambiente", "descricao": "Criação de ambiente"},
        {"nome": "excluir_ambiente", "descricao": "Exclusão lógica de ambiente"},
        {"nome": "reativar_ambiente", "descricao": "Reativação de ambiente"},
        {"nome": "associar_todos_usuarios_ambiente", "descricao": "Associação de todos os usuários convencionais a um ambiente"},
        {"nome": "associar_usuario_ambiente", "descricao": "Associação de usuário convencional a um ambiente"},
        {"nome": "excluir_vinculo_usuario_ambiente", "descricao": "Exclusão lógica de vínculo usuário-ambiente"},
        {"nome": "reativar_vinculo_usuario_ambiente", "descricao": "Reativação de vínculo usuário-ambiente"},
    ]
    for evento in eventos:
        existe = db.query(EventoAuditoria).filter_by(nome=evento["nome"]).first()
        if not existe:
            db.add(EventoAuditoria(nome=evento["nome"], descricao=evento["descricao"]))
    db.commit() 