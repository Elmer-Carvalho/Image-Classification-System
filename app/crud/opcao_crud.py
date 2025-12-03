"""
CRUD para operações com Opções.
"""
from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


def criar_opcao(db: Session, id_amb: str, texto: str) -> Optional[models.Opcao]:
    """
    Cria uma nova opção para um ambiente.
    
    Validações:
    - Ambiente deve existir e estar ativo
    - Texto não pode ser vazio ou só espaços
    - Texto não pode exceder 255 caracteres
    - Não pode existir opção com mesmo texto no mesmo ambiente
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
        texto: Texto da opção
    
    Returns:
        Opção criada ou None em caso de erro
    """
    # Validar e limpar texto
    texto_limpo = texto.strip() if texto else ""
    if not texto_limpo or len(texto_limpo) > 255:
        return None
    
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    # Verificar se ambiente existe e está ativo
    ambiente = db.query(models.Ambiente).filter(
        models.Ambiente.id_amb == id_amb_uuid,
        models.Ambiente.ativo == True
    ).first()
    
    if not ambiente:
        return None
    
    # Verificar se já existe opção com mesmo texto no mesmo ambiente
    opcao_existente = db.query(models.Opcao).filter_by(
        id_amb=id_amb_uuid,
        texto=texto_limpo
    ).first()
    
    if opcao_existente:
        return None
    
    # Criar opção
    nova_opcao = models.Opcao(
        texto=texto_limpo,
        id_amb=id_amb_uuid
    )
    
    try:
        db.add(nova_opcao)
        db.commit()
        db.refresh(nova_opcao)
        return nova_opcao
    except IntegrityError:
        db.rollback()
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao criar opção: {e}")
        return None


def listar_opcoes_ambiente(db: Session, id_amb: str) -> Optional[tuple[models.Ambiente, List[models.Opcao]]]:
    """
    Lista todas as opções de um ambiente.
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
    
    Returns:
        Tupla (ambiente, lista_opcoes) ou (None, []) se ambiente não encontrado
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None, []
    
    ambiente = db.query(models.Ambiente).filter_by(id_amb=id_amb_uuid).first()
    
    if not ambiente:
        return None, []
    
    # Buscar todas as opções do ambiente
    opcoes = db.query(models.Opcao).filter_by(id_amb=id_amb_uuid).order_by(models.Opcao.texto).all()
    
    return ambiente, opcoes


def buscar_opcao_por_id(db: Session, id_opc: str) -> Optional[models.Opcao]:
    """
    Busca uma opção por ID.
    
    Args:
        db: Sessão do banco de dados
        id_opc: ID da opção (UUID string)
    
    Returns:
        Opção ou None se não encontrada
    """
    try:
        id_opc_uuid = uuid.UUID(id_opc) if isinstance(id_opc, str) else id_opc
    except (ValueError, TypeError):
        return None
    
    return db.query(models.Opcao).filter_by(id_opc=id_opc_uuid).first()

