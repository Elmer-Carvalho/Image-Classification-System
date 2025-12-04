"""
CRUD para operações de classificação de imagens.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.db import models
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
import logging

logger = logging.getLogger(__name__)


def obter_progresso_usuario(db: Session, id_con: str, id_amb: str) -> Optional[models.UsuarioAmbienteProgresso]:
    """
    Busca ou cria o progresso do usuário em um ambiente.
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional
        id_amb: ID do ambiente
    
    Returns:
        Objeto UsuarioAmbienteProgresso
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    progresso = db.query(models.UsuarioAmbienteProgresso).filter_by(
        id_con=id_con_uuid,
        id_amb=id_amb_uuid
    ).first()
    
    if not progresso:
        # Criar progresso inicial
        progresso = models.UsuarioAmbienteProgresso(
            id_con=id_con_uuid,
            id_amb=id_amb_uuid,
            ultimo_data_proc_processado=None,
            ultimo_content_hash_processado=None,
            total_classificadas=0,
            data_ultima_atividade=datetime.now(timezone.utc)
        )
        db.add(progresso)
        db.commit()
        db.refresh(progresso)
    
    return progresso


def buscar_conjuntos_ambiente(db: Session, id_amb: str) -> List[uuid.UUID]:
    """
    Busca IDs dos conjuntos associados a um ambiente.
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente
    
    Returns:
        Lista de UUIDs dos conjuntos
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return []
    
    associacoes = db.query(models.AmbienteConjuntoImagens).filter(
        models.AmbienteConjuntoImagens.id_amb == id_amb_uuid,
        models.AmbienteConjuntoImagens.ativo == True
    ).all()
    
    return [assoc.id_cnj for assoc in associacoes]


def buscar_imagens_inicial(
    db: Session,
    id_amb: str,
    id_con: str,
    limit: int = 20
) -> Tuple[List[models.Imagem], bool]:
    """
    Busca as primeiras imagens não classificadas a partir do progresso do usuário.
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente
        id_con: ID do usuário convencional
        limit: Quantidade de imagens a retornar
    
    Returns:
        Tupla (lista_imagens, tem_mais)
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
    except (ValueError, TypeError):
        return [], False
    
    # Buscar progresso
    progresso = obter_progresso_usuario(db, id_con, id_amb)
    if not progresso:
        return [], False
    
    # Buscar conjuntos do ambiente
    conjuntos_ids = buscar_conjuntos_ambiente(db, id_amb)
    if not conjuntos_ids:
        return [], False
    
    # Buscar imagens já classificadas pelo usuário
    classificadas_subquery = db.query(models.Classificacao.id_img).filter_by(
        id_con=id_con_uuid
    )
    classificadas_hashes = [row[0] for row in classificadas_subquery.all()]
    
    # Query base
    query = db.query(models.Imagem).filter(
        models.Imagem.id_cnj.in_(conjuntos_ids),
        models.Imagem.existe_no_nextcloud == True
    )
    
    # Filtrar imagens já classificadas
    if classificadas_hashes:
        query = query.filter(~models.Imagem.content_hash.in_(classificadas_hashes))
    
    # Se há progresso, buscar a partir do cursor
    if progresso.ultimo_data_proc_processado and progresso.ultimo_content_hash_processado:
        query = query.filter(
            or_(
                models.Imagem.data_proc > progresso.ultimo_data_proc_processado,
                and_(
                    models.Imagem.data_proc == progresso.ultimo_data_proc_processado,
                    models.Imagem.content_hash > progresso.ultimo_content_hash_processado
                )
            )
        )
    
    # Ordenar e limitar
    imagens = query.order_by(
        models.Imagem.id_cnj,
        models.Imagem.data_proc,
        models.Imagem.content_hash
    ).limit(limit + 1).all()  # +1 para verificar se tem mais
    
    tem_mais = len(imagens) > limit
    if tem_mais:
        imagens = imagens[:limit]
    
    return imagens, tem_mais


def buscar_imagens_avancar(
    db: Session,
    id_amb: str,
    id_con: str,
    content_hash: str,
    limit: int = 20
) -> Tuple[List[models.Imagem], bool]:
    """
    Busca próximas imagens após uma imagem específica.
    Pode incluir imagens já classificadas.
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente
        id_con: ID do usuário convencional
        content_hash: Hash da imagem atual
        limit: Quantidade de imagens a retornar
    
    Returns:
        Tupla (lista_imagens, tem_mais)
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
    except (ValueError, TypeError):
        return [], False
    
    # Buscar a imagem de referência
    imagem_ref = db.query(models.Imagem).filter_by(content_hash=content_hash).first()
    if not imagem_ref:
        return [], False
    
    # Verificar se a imagem pertence ao ambiente
    conjuntos_ids = buscar_conjuntos_ambiente(db, id_amb)
    if imagem_ref.id_cnj not in conjuntos_ids:
        return [], False
    
    # Query para buscar próximas imagens
    query = db.query(models.Imagem).filter(
        models.Imagem.id_cnj.in_(conjuntos_ids),
        models.Imagem.existe_no_nextcloud == True,
        or_(
            models.Imagem.data_proc > imagem_ref.data_proc,
            and_(
                models.Imagem.data_proc == imagem_ref.data_proc,
                models.Imagem.content_hash > imagem_ref.content_hash
            )
        )
    )
    
    # Ordenar e limitar
    imagens = query.order_by(
        models.Imagem.id_cnj,
        models.Imagem.data_proc,
        models.Imagem.content_hash
    ).limit(limit + 1).all()
    
    tem_mais = len(imagens) > limit
    if tem_mais:
        imagens = imagens[:limit]
    
    return imagens, tem_mais


def buscar_imagens_voltar(
    db: Session,
    id_amb: str,
    id_con: str,
    content_hash: str,
    limit: int = 20
) -> Tuple[List[models.Imagem], bool]:
    """
    Busca imagens anteriores a uma imagem específica.
    Pode incluir imagens já classificadas.
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente
        id_con: ID do usuário convencional
        content_hash: Hash da imagem atual
        limit: Quantidade de imagens a retornar
    
    Returns:
        Tupla (lista_imagens, tem_mais)
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
    except (ValueError, TypeError):
        return [], False
    
    # Buscar a imagem de referência
    imagem_ref = db.query(models.Imagem).filter_by(content_hash=content_hash).first()
    if not imagem_ref:
        return [], False
    
    # Verificar se a imagem pertence ao ambiente
    conjuntos_ids = buscar_conjuntos_ambiente(db, id_amb)
    if imagem_ref.id_cnj not in conjuntos_ids:
        return [], False
    
    # Query para buscar imagens anteriores (ordem reversa)
    query = db.query(models.Imagem).filter(
        models.Imagem.id_cnj.in_(conjuntos_ids),
        models.Imagem.existe_no_nextcloud == True,
        or_(
            models.Imagem.data_proc < imagem_ref.data_proc,
            and_(
                models.Imagem.data_proc == imagem_ref.data_proc,
                models.Imagem.content_hash < imagem_ref.content_hash
            )
        )
    )
    
    # Ordenar reverso e limitar
    imagens = query.order_by(
        models.Imagem.id_cnj.desc(),
        models.Imagem.data_proc.desc(),
        models.Imagem.content_hash.desc()
    ).limit(limit + 1).all()
    
    # Reverter ordem para retornar do mais antigo ao mais recente
    imagens = list(reversed(imagens))
    
    tem_mais = len(imagens) > limit
    if tem_mais:
        imagens = imagens[:limit]
    
    return imagens, tem_mais


def obter_classificacoes_imagens(
    db: Session,
    id_con: str,
    imagens: List[models.Imagem]
) -> dict:
    """
    Busca classificações do usuário para uma lista de imagens.
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional
        imagens: Lista de imagens
    
    Returns:
        Dicionário {content_hash: Classificacao}
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
    except (ValueError, TypeError):
        return {}
    
    if not imagens:
        return {}
    
    content_hashes = [img.content_hash for img in imagens]
    
    classificacoes = db.query(models.Classificacao).filter(
        models.Classificacao.id_con == id_con_uuid,
        models.Classificacao.id_img.in_(content_hashes)
    ).all()
    
    return {c.id_img: c for c in classificacoes}


def criar_ou_atualizar_classificacao(
    db: Session,
    id_con: str,
    id_amb: str,
    content_hash: str,
    id_opc: str
) -> Tuple[Optional[models.Classificacao], bool]:
    """
    Cria ou atualiza uma classificação.
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional
        id_amb: ID do ambiente
        content_hash: Hash da imagem
        id_opc: ID da opção escolhida
    
    Returns:
        Tupla (classificacao, foi_criada)
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_opc_uuid = uuid.UUID(id_opc) if isinstance(id_opc, str) else id_opc
    except (ValueError, TypeError):
        return None, False
    
    # Verificar se imagem existe
    imagem = db.query(models.Imagem).filter_by(content_hash=content_hash).first()
    if not imagem:
        return None, False
    
    # Verificar se a imagem pertence ao ambiente
    conjuntos_ids = buscar_conjuntos_ambiente(db, id_amb)
    if imagem.id_cnj not in conjuntos_ids:
        return None, False
    
    # Verificar se opção existe e pertence ao ambiente
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None, False
    
    opcao = db.query(models.Opcao).filter_by(id_opc=id_opc_uuid, id_amb=id_amb_uuid).first()
    if not opcao:
        return None, False
    
    # Buscar classificação existente
    classificacao = db.query(models.Classificacao).filter_by(
        id_con=id_con_uuid,
        id_img=content_hash
    ).first()
    
    foi_criada = False
    if classificacao:
        # Atualizar existente
        classificacao.id_opc = id_opc_uuid
        classificacao.data_modificado = datetime.now(timezone.utc)
    else:
        # Criar nova
        classificacao = models.Classificacao(
            id_con=id_con_uuid,
            id_img=content_hash,
            id_opc=id_opc_uuid,
            data_criado=datetime.now(timezone.utc)
        )
        db.add(classificacao)
        foi_criada = True
    
    # Atualizar progresso
    progresso = obter_progresso_usuario(db, id_con, id_amb)
    if progresso:
        progresso.ultimo_data_proc_processado = imagem.data_proc
        progresso.ultimo_content_hash_processado = imagem.content_hash
        progresso.data_ultima_atividade = datetime.now(timezone.utc)
        if foi_criada:
            progresso.total_classificadas += 1
    
    try:
        db.commit()
        db.refresh(classificacao)
        return classificacao, foi_criada
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar classificação: {e}")
        return None, False

