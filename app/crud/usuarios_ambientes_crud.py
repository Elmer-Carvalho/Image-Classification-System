"""
CRUD para operações de associação entre Usuários Convencionais e Ambientes.
"""
from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
import logging

logger = logging.getLogger(__name__)


def listar_ambientes_usuario(db: Session, id_con: str) -> Optional[Tuple[models.UsuarioConvencional, List[dict]]]:
    """
    Lista ambientes do usuário com contagem de progresso.
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
    except (ValueError, TypeError):
        return None, []
    
    usuario = db.query(models.UsuarioConvencional).filter_by(id_con=id_con_uuid).first()
    
    if not usuario or not usuario.usuario.ativo:
        return None, []
    
    ambientes = []
    for vinc in usuario.ambientes:
        if vinc.ativo:
            amb = db.query(models.Ambiente).filter_by(id_amb=vinc.id_amb).first()
            if amb and amb.ativo:
                
                # 1. Calcular Total de Imagens do Ambiente
                # Busca os conjuntos vinculados ao ambiente
                conjuntos = db.query(models.AmbienteConjuntoImagens).filter(
                    models.AmbienteConjuntoImagens.id_amb == amb.id_amb,
                    models.AmbienteConjuntoImagens.ativo == True
                ).all()
                
                ids_conjuntos = [c.id_cnj for c in conjuntos]
                
                total_imagens = 0
                if ids_conjuntos:
                    # Conta imagens que existem no NextCloud e pertencem a esses conjuntos
                    total_imagens = db.query(models.Imagem).filter(
                        models.Imagem.id_cnj.in_(ids_conjuntos),
                        models.Imagem.existe_no_nextcloud == True
                    ).count()

                # 2. Calcular Quantas o Usuário Já Classificou
                progresso = db.query(models.UsuarioAmbienteProgresso).filter_by(
                    id_con=id_con_uuid,
                    id_amb=amb.id_amb
                ).first()
                
                total_classificadas = progresso.total_classificadas if progresso else 0

                # Adiciona na resposta
                ambientes.append({
                    "id_amb": str(amb.id_amb),
                    "titulo_amb": amb.titulo_amb,
                    "descricao_questionario": amb.descricao_questionario,
                    "ativo": amb.ativo,
                    "total_imagens": total_imagens,        # Novo
                    "total_classificadas": total_classificadas # Novo
                })
    
    return usuario, ambientes


def criar_associacoes(db: Session, id_amb: str, ids_usuarios: List[str]) -> Tuple[Optional[models.Ambiente], List[str]]:
    """
    Cria associações entre um ambiente e uma lista de usuários convencionais.
    
    Validações:
    - Ambiente deve existir e estar ativo
    - Todos os IDs de usuários devem ser válidos e existir
    - Usuários devem ser convencionais e estar ativos
    - Não cria associações duplicadas (se já existe e está ativa, ignora)
    - Não cria associações para administradores
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
        ids_usuarios: Lista de IDs de usuários convencionais (UUID strings)
    
    Returns:
        Tupla (ambiente, lista_ids_associados) ou (None, []) em caso de erro
    """
    if not ids_usuarios or len(ids_usuarios) == 0:
        return None, []
    
    # Remover duplicatas mantendo ordem
    ids_usuarios_unicos = list(dict.fromkeys(ids_usuarios))
    
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
        ids_usuarios_uuid = [uuid.UUID(id_con) for id_con in ids_usuarios_unicos]
    except ValueError:
        return None, []
    
    # Verificar se ambiente existe e está ativo
    ambiente = db.query(models.Ambiente).filter(
        models.Ambiente.id_amb == id_amb_uuid,
        models.Ambiente.ativo == True
    ).first()
    
    if not ambiente:
        return None, []
    
    # Validar que todos os usuários existem, são convencionais e estão ativos
    usuarios_validos = db.query(models.UsuarioConvencional).join(models.Usuario).filter(
        models.UsuarioConvencional.id_con.in_(ids_usuarios_uuid),
        models.Usuario.ativo == True
    ).all()
    
    ids_validos_encontrados = {str(usr.id_con) for usr in usuarios_validos}
    ids_solicitados = set(ids_usuarios_unicos)
    
    # Se algum ID não foi encontrado, retornar erro
    if ids_validos_encontrados != ids_solicitados:
        return None, []
    
    # Criar associações
    associados = []
    data_associado = datetime.now(timezone.utc)
    
    for id_con_uuid in ids_usuarios_uuid:
        # Verificar se associação já existe
        vinculo_existente = db.query(models.UsuarioAmbiente).filter_by(
            id_amb=id_amb_uuid,
            id_con=id_con_uuid
        ).first()
        
        if vinculo_existente:
            # Se já existe e está inativa, reativar
            if not vinculo_existente.ativo:
                vinculo_existente.ativo = True
                vinculo_existente.data_associado = data_associado
                associados.append(str(id_con_uuid))
            # Se já existe e está ativa, ignorar (não duplicar)
        else:
            # Criar nova associação
            novo_vinculo = models.UsuarioAmbiente(
                id_amb=id_amb_uuid,
                id_con=id_con_uuid,
                data_associado=data_associado,
                ativo=True
            )
            db.add(novo_vinculo)
            associados.append(str(id_con_uuid))
    
    try:
        db.commit()
        return ambiente, associados
    except IntegrityError:
        db.rollback()
        return None, []


def associar_todos_usuarios_ao_ambiente(db: Session, id_amb: str) -> Optional[int]:
    """
    Associa todos os usuários convencionais ativos a um ambiente.
    
    Validações:
    - Ambiente deve existir e estar ativo
    - Apenas usuários convencionais ativos são associados
    - Não cria associações duplicadas
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
    
    Returns:
        Número de usuários associados ou None se ambiente não encontrado
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    ambiente = db.query(models.Ambiente).filter(
        models.Ambiente.id_amb == id_amb_uuid,
        models.Ambiente.ativo == True
    ).first()
    
    if not ambiente:
        return None
    
    # Buscar todos os usuários convencionais ativos
    usuarios = db.query(models.UsuarioConvencional).join(models.Usuario).filter(
        models.Usuario.ativo == True
    ).all()
    
    count = 0
    data_associado = datetime.now(timezone.utc)
    
    for usuario in usuarios:
        vinculo = db.query(models.UsuarioAmbiente).filter_by(
            id_con=usuario.id_con,
            id_amb=id_amb_uuid
        ).first()
        
        if vinculo:
            # Se já existe e está inativa, reativar
            if not vinculo.ativo:
                vinculo.ativo = True
                vinculo.data_associado = data_associado
                count += 1
            # Se já existe e está ativa, ignorar
        else:
            # Criar nova associação
            novo = models.UsuarioAmbiente(
                id_con=usuario.id_con,
                id_amb=id_amb_uuid,
                data_associado=data_associado,
                ativo=True
            )
            db.add(novo)
            count += 1
    
    try:
        db.commit()
        return count
    except IntegrityError:
        db.rollback()
        return None


def excluir_associacao(db: Session, id_con: str, id_amb: str) -> Optional[models.UsuarioAmbiente]:
    """
    Exclui logicamente uma associação entre usuário convencional e ambiente.
    
    Validações:
    - Associação deve existir e estar ativa
    - Não tenta excluir associação já excluída
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional (UUID string)
        id_amb: ID do ambiente (UUID string)
    
    Returns:
        Associação excluída ou None se não encontrada
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    vinculo = db.query(models.UsuarioAmbiente).filter_by(
        id_amb=id_amb_uuid,
        id_con=id_con_uuid,
        ativo=True
    ).first()
    
    if vinculo:
        vinculo.ativo = False
        db.commit()
    
    return vinculo


def reativar_associacao(db: Session, id_con: str, id_amb: str) -> Optional[models.UsuarioAmbiente]:
    """
    Reativa logicamente uma associação entre usuário convencional e ambiente.
    
    Validações:
    - Associação deve existir e estar inativa
    - Ambiente deve estar ativo
    - Usuário deve estar ativo
    - Não tenta reativar associação já ativa
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional (UUID string)
        id_amb: ID do ambiente (UUID string)
    
    Returns:
        Associação reativada ou None se não encontrada ou não puder ser reativada
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    vinculo = db.query(models.UsuarioAmbiente).filter_by(
        id_amb=id_amb_uuid,
        id_con=id_con_uuid,
        ativo=False
    ).first()
    
    if not vinculo:
        return None
    
    # Verificar se ambiente está ativo
    ambiente = db.query(models.Ambiente).filter_by(
        id_amb=id_amb_uuid,
        ativo=True
    ).first()
    
    if not ambiente:
        return None
    
    # Verificar se usuário está ativo
    usuario = db.query(models.UsuarioConvencional).join(models.Usuario).filter(
        models.UsuarioConvencional.id_con == id_con_uuid,
        models.Usuario.ativo == True
    ).first()
    
    if not usuario:
        return None
    
    vinculo.ativo = True
    vinculo.data_associado = datetime.now(timezone.utc)  # Atualizar data
    db.commit()
    
    return vinculo


def obter_associacao_por_ids(db: Session, id_con: str, id_amb: str) -> Optional[models.UsuarioAmbiente]:
    """
    Obtém uma associação específica por IDs.
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional (UUID string)
        id_amb: ID do ambiente (UUID string)
    
    Returns:
        Associação ou None se não encontrada
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    return db.query(models.UsuarioAmbiente).filter_by(
        id_amb=id_amb_uuid,
        id_con=id_con_uuid
    ).first()


def listar_usuarios_do_ambiente(db: Session, id_amb: str) -> Optional[Tuple[models.Ambiente, List[dict]]]:
    """
    Lista todos os usuários convencionais associados a um ambiente (apenas ativos).
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
    
    Returns:
        Tupla (ambiente, lista_usuarios) ou (None, []) se ambiente não encontrado
    """
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None, []
    
    ambiente = db.query(models.Ambiente).filter_by(id_amb=id_amb_uuid).first()
    
    if not ambiente:
        return None, []
    
    # Buscar todas as associações ativas deste ambiente
    associacoes = db.query(models.UsuarioAmbiente).filter(
        models.UsuarioAmbiente.id_amb == id_amb_uuid,
        models.UsuarioAmbiente.ativo == True
    ).all()
    
    usuarios = []
    for vinc in associacoes:
        usuario_conv = db.query(models.UsuarioConvencional).filter_by(
            id_con=vinc.id_con
        ).first()
        
        if usuario_conv and usuario_conv.usuario.ativo:
            usuarios.append({
                "id_con": str(usuario_conv.id_con),
                "nome_completo": usuario_conv.usuario.nome_completo,
                "email": usuario_conv.usuario.email,
                "ativo": usuario_conv.usuario.ativo,
                "data_associado": vinc.data_associado
            })
    
    return ambiente, usuarios
