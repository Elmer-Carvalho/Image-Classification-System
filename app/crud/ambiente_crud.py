from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from typing import List, Optional
import uuid


def criar_ambiente(db: Session, titulo_amb: str, titulo_questionario: Optional[str], descricao_questionario: str, id_adm, ids_conjuntos: List[str], opcoes: List[str]):
    """
    Cria um novo ambiente, associa aos conjuntos de imagens e cria as opções.
    
    Args:
        db: Sessão do banco de dados
        titulo_amb: Título do ambiente
        titulo_questionario: Título do questionário (opcional)
        descricao_questionario: Descrição do questionário (obrigatório)
        id_adm: ID do administrador
        ids_conjuntos: Lista de IDs de ConjuntoImagens (mínimo 1)
        opcoes: Lista de textos de opções (mínimo 2)
    
    Returns:
        Tupla (ambiente, lista_ids_validos) ou (None, []) em caso de erro
    """
    # Validar que há pelo menos 1 conjunto
    if not ids_conjuntos or len(ids_conjuntos) == 0:
        return None, []
    
    # Validar que há pelo menos 2 opções
    if not opcoes or len(opcoes) < 2:
        return None, []
    
    # Validar e limpar textos de opções (remover espaços, verificar não vazios)
    opcoes_validas = []
    for texto in opcoes:
        texto_limpo = texto.strip() if texto else ""
        if texto_limpo and len(texto_limpo) <= 255:
            opcoes_validas.append(texto_limpo)
    
    # Se após validação tiver menos de 2 opções válidas, retornar erro
    if len(opcoes_validas) < 2:
        return None, []
    
    # Remover duplicatas mantendo ordem
    ids_conjuntos_unicos = list(dict.fromkeys(ids_conjuntos))
    opcoes_unicas = list(dict.fromkeys(opcoes_validas))
    
    # Validar que todos os IDs de conjuntos existem no banco (em uma única query)
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
        titulo_questionario=titulo_questionario.strip() if titulo_questionario else None,
        descricao_questionario=descricao_questionario,
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
        
        # Criar opções (garantir atomicidade - se falhar, rollback completo)
        for texto_opcao in opcoes_unicas:
            # Verificar se já existe opção com mesmo texto no mesmo ambiente
            opcao_existente = db.query(models.Opcao).filter_by(
                id_amb=novo.id_amb,
                texto=texto_opcao
            ).first()
            
            if opcao_existente:
                # Se já existe, fazer rollback e retornar erro
                db.rollback()
                return None, []
            
            nova_opcao = models.Opcao(
                texto=texto_opcao,
                id_amb=novo.id_amb
            )
            db.add(nova_opcao)
        
        db.commit()
        db.refresh(novo)
        return novo, ids_conjuntos_unicos
    except IntegrityError:
        db.rollback()
        return None, []
    except Exception as e:
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


def atualizar_titulo_ambiente(db: Session, id_amb: str, novo_titulo: str) -> Optional[models.Ambiente]:
    """
    Atualiza o título de um ambiente.
    
    Validações:
    - Ambiente deve existir
    - Novo título não pode ser vazio ou só espaços
    - Novo título não pode exceder 255 caracteres
    - Novo título deve ser único
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
        novo_titulo: Novo título do ambiente
    
    Returns:
        Ambiente atualizado ou None em caso de erro
    """
    # Validar e limpar título
    titulo_limpo = novo_titulo.strip() if novo_titulo else ""
    if not titulo_limpo or len(titulo_limpo) < 3 or len(titulo_limpo) > 255:
        return None
    
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    # Buscar ambiente
    ambiente = db.query(models.Ambiente).filter_by(id_amb=id_amb_uuid).first()
    
    if not ambiente:
        return None
    
    # Verificar se novo título já existe em outro ambiente
    ambiente_existente = db.query(models.Ambiente).filter(
        models.Ambiente.titulo_amb == titulo_limpo,
        models.Ambiente.id_amb != id_amb_uuid
    ).first()
    
    if ambiente_existente:
        return None
    
    # Atualizar título
    ambiente.titulo_amb = titulo_limpo
    
    try:
        db.commit()
        db.refresh(ambiente)
        return ambiente
    except IntegrityError:
        db.rollback()
        return None
    except Exception as e:
        db.rollback()
        return None


def atualizar_descricao_questionario(db: Session, id_amb: str, nova_descricao: str) -> Optional[models.Ambiente]:
    """
    Atualiza a descrição do questionário de um ambiente.
    
    Validações:
    - Ambiente deve existir
    - Nova descrição não pode ser vazia ou só espaços
    - Nova descrição deve ter no mínimo 3 caracteres
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
        nova_descricao: Nova descrição do questionário
    
    Returns:
        Ambiente atualizado ou None em caso de erro
    """
    # Validar e limpar descrição
    descricao_limpa = nova_descricao.strip() if nova_descricao else ""
    if not descricao_limpa or len(descricao_limpa) < 3:
        return None
    
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    # Buscar ambiente
    ambiente = db.query(models.Ambiente).filter_by(id_amb=id_amb_uuid).first()
    
    if not ambiente:
        return None
    
    # Atualizar descrição
    ambiente.descricao_questionario = descricao_limpa
    
    try:
        db.commit()
        db.refresh(ambiente)
        return ambiente
    except Exception as e:
        db.rollback()
        return None


def atualizar_titulo_questionario(db: Session, id_amb: str, novo_titulo: Optional[str]) -> Optional[models.Ambiente]:
    """
    Atualiza o título do questionário de um ambiente.
    
    Validações:
    - Ambiente deve existir
    - Se fornecido, novo título não pode ser só espaços
    - Novo título não pode exceder 255 caracteres
    
    Args:
        db: Sessão do banco de dados
        id_amb: ID do ambiente (UUID string)
        novo_titulo: Novo título do questionário (pode ser None para remover)
    
    Returns:
        Ambiente atualizado ou None em caso de erro
    """
    # Validar e limpar título (pode ser None)
    titulo_limpo = None
    if novo_titulo is not None:
        titulo_temp = novo_titulo.strip() if novo_titulo else ""
        if titulo_temp:
            if len(titulo_temp) > 255:
                return None
            titulo_limpo = titulo_temp
    
    try:
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return None
    
    # Buscar ambiente
    ambiente = db.query(models.Ambiente).filter_by(id_amb=id_amb_uuid).first()
    
    if not ambiente:
        return None
    
    # Atualizar título
    ambiente.titulo_questionario = titulo_limpo
    
    try:
        db.commit()
        db.refresh(ambiente)
        return ambiente
    except Exception as e:
        db.rollback()
        return None
