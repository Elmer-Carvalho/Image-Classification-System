from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from typing import List, Optional
import uuid


def criar_ambiente(db: Session, titulo_amb: str, descricao: str, id_adm, ids_conjuntos: List[str]):
    """
    Cria um novo ambiente e associa aos conjuntos de imagens fornecidos.
    
    Args:
        db: Sessão do banco de dados
        titulo_amb: Título do ambiente
        descricao: Descrição do ambiente
        id_adm: ID do administrador
        ids_conjuntos: Lista de IDs de ConjuntoImagens (mínimo 1)
    
    Returns:
        Tupla (ambiente, lista_ids_validos) ou (None, []) em caso de erro
    """
    # Validar que há pelo menos 1 conjunto
    if not ids_conjuntos or len(ids_conjuntos) == 0:
        return None, []
    
    # Remover duplicatas mantendo ordem
    ids_conjuntos_unicos = list(dict.fromkeys(ids_conjuntos))
    
    # Validar que todos os IDs existem no banco (em uma única query)
    try:
        ids_uuid = [uuid.UUID(id_cnj) for id_cnj in ids_conjuntos_unicos]
    except ValueError:
        # IDs inválidos (não são UUIDs válidos)
        return None, []
    
    conjuntos_validos = db.query(models.ConjuntoImagens).filter(
        models.ConjuntoImagens.id_cnj.in_(ids_uuid)
    ).all()
    
    ids_validos_encontrados = {str(cnj.id_cnj) for cnj in conjuntos_validos}
    ids_solicitados = set(ids_conjuntos_unicos)
    
    # Se algum ID não foi encontrado, retornar erro
    if ids_validos_encontrados != ids_solicitados:
        return None, []
    
    # Criar ambiente
    novo = models.Ambiente(
        titulo_amb=titulo_amb,
        descricao=descricao,
        data_criado=datetime.now(timezone.utc),
        id_adm=id_adm,
        ativo=True
    )
    db.add(novo)
    
    try:
        db.flush()  # Obter ID do ambiente sem fazer commit
        data_associado = datetime.now(timezone.utc)
        
        # Criar associações na tabela auxiliar
        for id_cnj_uuid in ids_uuid:
            associacao = models.AmbienteConjuntoImagens(
                id_amb=novo.id_amb,
                id_cnj=id_cnj_uuid,
                data_associado=data_associado,
                ativo=True
            )
            db.add(associacao)
        
        db.commit()
        db.refresh(novo)
        return novo, ids_conjuntos_unicos
    except IntegrityError:
        db.rollback()
        return None, []


def listar_ambientes(db: Session):
    """Lista todos os ambientes."""
    return db.query(models.Ambiente).all()


def buscar_ambiente_por_titulo(db: Session, titulo_amb: str):
    """Busca ambiente por título."""
    return db.query(models.Ambiente).filter(models.Ambiente.titulo_amb == titulo_amb).first()


def buscar_ambiente_por_id(db: Session, id_amb):
    """Busca ambiente por ID."""
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
        return db.query(models.Ambiente).filter(models.Ambiente.id_amb == id_amb_uuid).first()
    except (ValueError, TypeError):
        return None


def excluir_ambiente(db: Session, id_amb):
    """
    Realiza exclusão lógica do ambiente e de todas suas associações com conjuntos.
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID ou string)
    
    Returns:
        Ambiente excluído ou None se não encontrado
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    ambiente = db.query(models.Ambiente).filter(
        models.Ambiente.id_amb == id_amb_uuid,
        models.Ambiente.ativo == True
    ).first()
    
    if ambiente:
        # Excluir logicamente o ambiente
        ambiente.ativo = False
        
        # Excluir logicamente todas as associações com conjuntos em cascata
        associacoes_conjuntos = db.query(models.AmbienteConjuntoImagens).filter(
            models.AmbienteConjuntoImagens.id_amb == id_amb_uuid,
            models.AmbienteConjuntoImagens.ativo == True
        ).all()
        
        for associacao in associacoes_conjuntos:
            associacao.ativo = False
        
        # Excluir logicamente todas as associações com usuários em cascata
        associacoes_usuarios = db.query(models.UsuarioAmbiente).filter(
            models.UsuarioAmbiente.id_amb == id_amb_uuid,
            models.UsuarioAmbiente.ativo == True
        ).all()
        
        for associacao in associacoes_usuarios:
            associacao.ativo = False
        
        db.commit()
    
    return ambiente


def reativar_ambiente(db: Session, id_amb):
    """
    Reativa um ambiente e suas associações, mas apenas se os conjuntos ainda existem no NextCloud.
    
    Regras:
    - Reativa associações apenas se o conjunto tiver existe_no_nextcloud = True
    - Se nenhuma associação puder ser reativada, o ambiente não é reativado
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID ou string)
    
    Returns:
        Ambiente reativado ou None se não encontrado ou se não foi possível reativar
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    ambiente = db.query(models.Ambiente).filter(
        models.Ambiente.id_amb == id_amb_uuid,
        models.Ambiente.ativo == False
    ).first()
    
    if not ambiente:
        return None
    
    # Buscar todas as associações inativas deste ambiente (conjuntos e usuários)
    associacoes_conjuntos = db.query(models.AmbienteConjuntoImagens).filter(
        models.AmbienteConjuntoImagens.id_amb == id_amb_uuid,
        models.AmbienteConjuntoImagens.ativo == False
    ).all()
    
    associacoes_usuarios = db.query(models.UsuarioAmbiente).filter(
        models.UsuarioAmbiente.id_amb == id_amb_uuid,
        models.UsuarioAmbiente.ativo == False
    ).all()
    
    if not associacoes_conjuntos and not associacoes_usuarios:
        # Não há associações para reativar
        return None
    
    # Verificar quais conjuntos ainda existem no NextCloud
    associacoes_conjuntos_reativadas = 0
    if associacoes_conjuntos:
        ids_conjuntos = [assoc.id_cnj for assoc in associacoes_conjuntos]
        conjuntos_validos = db.query(models.ConjuntoImagens).filter(
            models.ConjuntoImagens.id_cnj.in_(ids_conjuntos),
            models.ConjuntoImagens.existe_no_nextcloud == True
        ).all()
        
        ids_conjuntos_validos = {cnj.id_cnj for cnj in conjuntos_validos}
        
        # Reativar apenas as associações com conjuntos válidos
        for associacao in associacoes_conjuntos:
            if associacao.id_cnj in ids_conjuntos_validos:
                associacao.ativo = True
                associacoes_conjuntos_reativadas += 1
    
    # Reativar associações com usuários (verificar se usuários ainda estão ativos)
    associacoes_usuarios_reativadas = 0
    for associacao in associacoes_usuarios:
        # Verificar se o usuário convencional ainda está ativo
        usuario_conv = db.query(models.UsuarioConvencional).filter_by(
            id_con=associacao.id_con
        ).first()
        
        if usuario_conv and usuario_conv.usuario.ativo:
            associacao.ativo = True
            associacoes_usuarios_reativadas += 1
    
    # Reativar ambiente apenas se pelo menos uma associação (conjunto ou usuário) foi reativada
    if associacoes_conjuntos_reativadas > 0 or associacoes_usuarios_reativadas > 0:
        ambiente.ativo = True
        db.commit()
        return ambiente
    
    return None


def obter_conjuntos_do_ambiente(db: Session, id_amb):
    """
    Retorna lista de IDs de conjuntos associados a um ambiente (apenas ativos).
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID ou string)
    
    Returns:
        Lista de IDs de conjuntos (strings)
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return []
    
    associacoes = db.query(models.AmbienteConjuntoImagens).filter(
        models.AmbienteConjuntoImagens.id_amb == id_amb_uuid,
        models.AmbienteConjuntoImagens.ativo == True
    ).all()
    
    return [str(assoc.id_cnj) for assoc in associacoes]
