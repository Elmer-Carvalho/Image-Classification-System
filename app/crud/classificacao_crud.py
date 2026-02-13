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
    
    # Buscar imagens já classificadas pelo usuário (apenas classificações ativas)
    classificadas_subquery = db.query(models.Classificacao.id_img).filter(
        models.Classificacao.id_con == id_con_uuid,
        models.Classificacao.ativo == True
    ).distinct()
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
    Busca classificações ativas do usuário para uma lista de imagens.
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional
        imagens: Lista de imagens
    
    Returns:
        Dicionário {content_hash: List[Classificacao]} - Lista de classificações por imagem
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
    except (ValueError, TypeError):
        return {}
    
    if not imagens:
        return {}
    
    content_hashes = [img.content_hash for img in imagens]
    
    # Buscar apenas classificações ativas
    classificacoes = db.query(models.Classificacao).filter(
        models.Classificacao.id_con == id_con_uuid,
        models.Classificacao.id_img.in_(content_hashes),
        models.Classificacao.ativo == True
    ).all()
    
    # Agrupar por content_hash (múltiplas classificações por imagem)
    resultado = {}
    for c in classificacoes:
        if c.id_img not in resultado:
            resultado[c.id_img] = []
        resultado[c.id_img].append(c)
    
    return resultado


def criar_ou_atualizar_classificacao(
    db: Session,
    id_con: str,
    id_amb: str,
    content_hash: str,
    id_opc: List[str]
) -> Tuple[List[models.Classificacao], int]:
    """
    Cria ou atualiza classificações para uma imagem com múltiplas opções.
    Implementa lógica de reclassificação: inativa classificações antigas que não estão na nova lista.
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional
        id_amb: ID do ambiente
        content_hash: Hash da imagem
        id_opc: Lista de IDs das opções escolhidas
    
    Returns:
        Tupla (lista_classificacoes_criadas_atualizadas, total_novas_criadas)
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
        
        # Converter lista de opções para UUIDs
        id_opc_uuids = []
        for opc_id in id_opc:
            try:
                id_opc_uuids.append(uuid.UUID(opc_id) if isinstance(opc_id, str) else opc_id)
            except (ValueError, TypeError):
                logger.warning(f"ID de opção inválido: {opc_id}")
                continue
        
        if not id_opc_uuids:
            return [], 0
            
    except (ValueError, TypeError) as e:
        logger.error(f"Erro ao converter IDs: {e}")
        return [], 0
    
    # Verificar se imagem existe
    imagem = db.query(models.Imagem).filter_by(content_hash=content_hash).first()
    if not imagem:
        logger.warning(f"Imagem não encontrada: {content_hash}")
        return [], 0
    
    # Verificar se a imagem pertence ao ambiente
    conjuntos_ids = buscar_conjuntos_ambiente(db, id_amb)
    if imagem.id_cnj not in conjuntos_ids:
        logger.warning(f"Imagem não pertence ao ambiente: {content_hash}")
        return [], 0
    
    # Verificar se todas as opções existem e pertencem ao ambiente
    opcoes_validas = {}
    for id_opc_uuid in id_opc_uuids:
        opcao = db.query(models.Opcao).filter_by(id_opc=id_opc_uuid, id_amb=id_amb_uuid).first()
        if not opcao:
            logger.warning(f"Opção não encontrada ou não pertence ao ambiente: {id_opc_uuid}")
            continue
        opcoes_validas[id_opc_uuid] = opcao
    
    if not opcoes_validas:
        logger.warning("Nenhuma opção válida fornecida")
        return [], 0
    
    # Buscar TODAS as classificações existentes (ativas E inativas) para esta imagem e usuário
    # Isso permite reativar classificações que estavam inativas
    classificacoes_existentes = db.query(models.Classificacao).filter(
        models.Classificacao.id_con == id_con_uuid,
        models.Classificacao.id_img == content_hash
        # Não filtrar por ativo - buscar todas para poder reativar
    ).all()
    
    # Criar dicionário de classificações existentes por opção
    classificacoes_por_opcao = {c.id_opc: c for c in classificacoes_existentes}
    
    # Separar classificações ativas e inativas
    classificacoes_ativas = {c.id_opc: c for c in classificacoes_existentes if c.ativo}
    classificacoes_inativas = {c.id_opc: c for c in classificacoes_existentes if not c.ativo}
    
    # Identificar quais opções já existem e quais são novas
    opcoes_para_manter = set(opcoes_validas.keys())
    opcoes_existentes_ativas = set(classificacoes_ativas.keys())
    opcoes_existentes_inativas = set(classificacoes_inativas.keys())
    opcoes_existentes_todas = opcoes_existentes_ativas | opcoes_existentes_inativas
    
    # Opções que devem ser inativadas (existem ativas mas não estão na nova lista)
    opcoes_para_inativar = opcoes_existentes_ativas - opcoes_para_manter
    
    # Opções novas que precisam ser criadas (não existem em nenhuma forma)
    opcoes_para_criar = opcoes_para_manter - opcoes_existentes_todas
    
    # Opções que já existem ativas e devem ser mantidas
    opcoes_para_manter_ativas = opcoes_para_manter & opcoes_existentes_ativas
    
    # Opções que existem inativas e devem ser reativadas
    opcoes_para_reativar = opcoes_para_manter & opcoes_existentes_inativas
    
    agora = datetime.now(timezone.utc)
    classificacoes_resultado = []
    total_novas = 0
    
    try:
        # 1. Inativar classificações que não estão mais na lista
        if opcoes_para_inativar:
            db.query(models.Classificacao).filter(
                models.Classificacao.id_con == id_con_uuid,
                models.Classificacao.id_img == content_hash,
                models.Classificacao.id_opc.in_(opcoes_para_inativar),
                models.Classificacao.ativo == True
            ).update(
                {'ativo': False, 'data_modificado': agora},
                synchronize_session=False
            )
            logger.info(f"Inativadas {len(opcoes_para_inativar)} classificações para imagem {content_hash}")
        
        # 2. Reativar classificações que estavam inativas mas estão na nova lista
        if opcoes_para_reativar:
            for id_opc_uuid in opcoes_para_reativar:
                classificacao = classificacoes_inativas[id_opc_uuid]
                # Reativar classificação que estava inativa
                classificacao.ativo = True
                classificacao.data_modificado = agora
                classificacoes_resultado.append(classificacao)
            logger.info(f"Reativadas {len(opcoes_para_reativar)} classificações para imagem {content_hash}")
        
        # 3. Adicionar classificações que já estavam ativas e devem ser mantidas
        if opcoes_para_manter_ativas:
            for id_opc_uuid in opcoes_para_manter_ativas:
                classificacao = classificacoes_ativas[id_opc_uuid]
                # Já está ativa, apenas adicionar ao resultado
                classificacoes_resultado.append(classificacao)
        
        # 4. Criar novas classificações para opções que não existiam
        novas_classificacoes = []
        for id_opc_uuid in opcoes_para_criar:
            nova_classificacao = models.Classificacao(
                id_con=id_con_uuid,
                id_img=content_hash,
                id_opc=id_opc_uuid,
                data_criado=agora,
                ativo=True
            )
            novas_classificacoes.append(nova_classificacao)
            classificacoes_resultado.append(nova_classificacao)
            total_novas += 1
        
        if novas_classificacoes:
            db.bulk_save_objects(novas_classificacoes)
            logger.info(f"Criadas {len(novas_classificacoes)} novas classificações para imagem {content_hash}")
        
        # 5. Atualizar progresso do usuário
        progresso = obter_progresso_usuario(db, id_con, id_amb)
        if progresso:
            progresso.ultimo_data_proc_processado = imagem.data_proc
            progresso.ultimo_content_hash_processado = imagem.content_hash
            progresso.data_ultima_atividade = agora
            
            # Atualizar contagem de imagens classificadas
            # Incrementa apenas se:
            # 1. Houver novas classificações criadas OU
            # 2. Houver reativações E a imagem não tinha nenhuma classificação ativa antes
            tinha_classificacao_ativa_antes = len(opcoes_existentes_ativas) > 0
            
            if total_novas > 0 or (opcoes_para_reativar and not tinha_classificacao_ativa_antes):
                # Primeira vez classificando esta imagem (ou primeira vez após todas terem sido inativadas)
                if not tinha_classificacao_ativa_antes:
                    progresso.total_classificadas += 1
        
        db.commit()
        
        # Refresh das novas classificações
        for c in novas_classificacoes:
            db.refresh(c)
        
        logger.info(f"Classificação concluída: {len(classificacoes_resultado)} classificações ativas, {total_novas} novas")
        return classificacoes_resultado, total_novas
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar classificação: {e}", exc_info=True)
        return [], 0

