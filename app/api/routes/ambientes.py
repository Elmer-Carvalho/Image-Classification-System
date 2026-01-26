from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin
from app.schemas.auth_schema import (
    AmbienteCreate, 
    AmbienteOut,
    AmbienteUpdateTitulo,
    AmbienteUpdateDescricaoQuestionario,
    AmbienteUpdateTituloQuestionario
)
from app.crud import ambiente_crud
from app.db import models
from datetime import datetime, timezone
from app.db.models import EventoAuditoria, LogAuditoria

router = APIRouter(prefix="/ambientes", tags=["Ambientes"])

@router.post("/importar", response_model=AmbienteOut, status_code=201)
def criar_ambiente(
    ambiente: AmbienteCreate = Body(...),
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Cria um novo ambiente associado a um ou mais conjuntos de imagens.
    - **Acesso:** Apenas administradores autenticados.
    - **Regras:** 
      - Título único, título e descrição obrigatórios
      - Deve ter pelo menos 1 conjunto de imagens associado
      - Todos os IDs de conjuntos devem existir e ser válidos
    - **Respostas:**
      - 201: Ambiente criado
      - 400: Lista de conjuntos vazia ou IDs inválidos
      - 409: Título já existe
      - 422: Erros de validação
    """
    # Validar que há pelo menos 1 conjunto
    if not ambiente.ids_conjuntos or len(ambiente.ids_conjuntos) == 0:
        exc = HTTPException(
            status_code=400,
            detail="Um ambiente deve estar associado a pelo menos 1 conjunto de imagens."
        )
        exc.code = "ids_conjuntos_empty"
        raise exc
    
    # Validar que há pelo menos 2 opções
    if not ambiente.opcoes or len(ambiente.opcoes) < 2:
        exc = HTTPException(
            status_code=400,
            detail="Um ambiente deve ter pelo menos 2 opções."
        )
        exc.code = "opcoes_minimum"
        raise exc
    
    if ambiente_crud.buscar_ambiente_por_titulo(db, ambiente.titulo_amb):
        exc = HTTPException(status_code=409, detail="Já existe um ambiente com este título.")
        exc.code = "ambiente_title_exists"
        raise exc
    
    novo, ids_validos = ambiente_crud.criar_ambiente(
        db, 
        ambiente.titulo_amb,
        ambiente.titulo_questionario,
        ambiente.descricao_questionario,
        admin.administrador.id_adm,
        ambiente.ids_conjuntos,
        ambiente.opcoes
    )
    
    if not novo:
        exc = HTTPException(
            status_code=400,
            detail="Não foi possível criar o ambiente. Verifique se todos os IDs de conjuntos são válidos, se há pelo menos 2 opções válidas, e se não há opções duplicadas."
        )
        exc.code = "invalid_data"
        raise exc
    
    nome_adm = admin.nome_completo
    
    # Obter IDs de conjuntos associados
    ids_conjuntos_associados = ambiente_crud.obter_conjuntos_do_ambiente(db, novo.id_amb)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="criar_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={
                "id_amb": str(novo.id_amb),
                "titulo_amb": novo.titulo_amb,
                "ids_conjuntos": ids_conjuntos_associados
            }
        )
        db.add(log)
        db.commit()
    
    return AmbienteOut(
        id_amb=str(novo.id_amb),
        titulo_amb=novo.titulo_amb,
        titulo_questionario=novo.titulo_questionario,
        descricao_questionario=novo.descricao_questionario,
        data_criado=novo.data_criado,
        id_adm=str(novo.id_adm),
        nome_administrador=nome_adm,
        ativo=novo.ativo,
        ids_conjuntos=ids_conjuntos_associados
    )

@router.get("/", response_model=list[AmbienteOut])
def listar_ambientes(
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos os ambientes.
    - **Acesso:** Apenas administradores autenticados.
    - **Resposta:** Lista de ambientes com informações completas, incluindo IDs dos conjuntos associados.
    """
    ambientes = ambiente_crud.listar_ambientes(db)
    result = []
    for a in ambientes:
        nome_adm = a.administrador.usuario.nome_completo if a.administrador and a.administrador.usuario else "(desconhecido)"
        ids_conjuntos = ambiente_crud.obter_conjuntos_do_ambiente(db, a.id_amb)
        result.append(
            AmbienteOut(
                id_amb=str(a.id_amb),
                titulo_amb=a.titulo_amb,
                titulo_questionario=a.titulo_questionario,
                descricao_questionario=a.descricao_questionario,
                data_criado=a.data_criado,
                id_adm=str(a.id_adm),
                nome_administrador=nome_adm,
                ativo=a.ativo,
                ids_conjuntos=ids_conjuntos
            )
        )
    return result

@router.delete("/{id_amb}", status_code=204)
def excluir_ambiente_route(id_amb: str, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Realiza a exclusão lógica (desativação) de um ambiente pelo ID.
    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 204: Ambiente desativado com sucesso
      - 404: Ambiente não encontrado ou já inativo
    """
    ambiente = ambiente_crud.excluir_ambiente(db, id_amb)
    if not ambiente:
        exc = HTTPException(status_code=404, detail="Ambiente não encontrado ou já inativo.")
        exc.code = "ambiente_not_found"
        raise exc
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="excluir_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb}
        )
        db.add(log)
        db.commit()
    return

@router.patch("/{id_amb}/reativar", status_code=200)
def reativar_ambiente_route(id_amb: str, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Reativa um ambiente desativado pelo ID.
    
    Regras de reativação:
    - Reativa associações apenas se os conjuntos ainda existem no NextCloud (existe_no_nextcloud = True)
    - Se nenhuma associação puder ser reativada, o ambiente não é reativado
    
    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 200: Ambiente reativado com sucesso
      - 404: Ambiente não encontrado, já ativo, ou não foi possível reativar (nenhum conjunto válido)
    """
    ambiente = ambiente_crud.reativar_ambiente(db, id_amb)
    if not ambiente:
        exc = HTTPException(
            status_code=404, 
            detail="Ambiente não encontrado, já ativo, ou não foi possível reativar (nenhum conjunto de imagens válido encontrado no NextCloud)."
        )
        exc.code = "ambiente_not_found_or_cannot_reactivate"
        raise exc
    nome_adm = ambiente.administrador.usuario.nome_completo if ambiente.administrador and ambiente.administrador.usuario else "(desconhecido)"
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="reativar_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb}
        )
        db.add(log)
        db.commit()
    ids_conjuntos = ambiente_crud.obter_conjuntos_do_ambiente(db, ambiente.id_amb)
    return {
        "message": "Ambiente reativado com sucesso.",
        "ambiente": AmbienteOut(
            id_amb=str(ambiente.id_amb),
            titulo_amb=ambiente.titulo_amb,
            titulo_questionario=ambiente.titulo_questionario,
            descricao_questionario=ambiente.descricao_questionario,
            data_criado=ambiente.data_criado,
            id_adm=str(ambiente.id_adm),
            nome_administrador=nome_adm,
            ativo=ambiente.ativo,
            ids_conjuntos=ids_conjuntos
        )
    }


@router.patch("/{id_amb}/titulo", response_model=AmbienteOut, status_code=200)
def atualizar_titulo_ambiente(
    id_amb: str,
    payload: AmbienteUpdateTitulo = Body(...),
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Atualiza o título de um ambiente.
    
    - **Acesso:** Apenas administradores autenticados.
    - **Validações:**
      - Título não pode ser vazio ou só espaços
      - Título deve ter entre 3 e 255 caracteres
      - Título deve ser único
    - **Respostas:**
      - 200: Título atualizado com sucesso
      - 400: Título inválido ou já existe
      - 404: Ambiente não encontrado
    """
    ambiente = ambiente_crud.atualizar_titulo_ambiente(db, id_amb, payload.titulo_amb)
    
    if not ambiente:
        exc = HTTPException(
            status_code=400,
            detail="Não foi possível atualizar o título. Verifique se o título é válido e não está em uso por outro ambiente."
        )
        exc.code = "invalid_titulo"
        raise exc
    
    nome_adm = ambiente.administrador.usuario.nome_completo if ambiente.administrador and ambiente.administrador.usuario else "(desconhecido)"
    ids_conjuntos = ambiente_crud.obter_conjuntos_do_ambiente(db, ambiente.id_amb)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="atualizar_titulo_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb, "novo_titulo": payload.titulo_amb}
        )
        db.add(log)
        db.commit()
    
    return AmbienteOut(
        id_amb=str(ambiente.id_amb),
        titulo_amb=ambiente.titulo_amb,
        titulo_questionario=ambiente.titulo_questionario,
        descricao_questionario=ambiente.descricao_questionario,
        data_criado=ambiente.data_criado,
        id_adm=str(ambiente.id_adm),
        nome_administrador=nome_adm,
        ativo=ambiente.ativo,
        ids_conjuntos=ids_conjuntos
    )


@router.patch("/{id_amb}/descricao-questionario", response_model=AmbienteOut, status_code=200)
def atualizar_descricao_questionario(
    id_amb: str,
    payload: AmbienteUpdateDescricaoQuestionario = Body(...),
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Atualiza a descrição do questionário de um ambiente.
    
    - **Acesso:** Apenas administradores autenticados.
    - **Validações:**
      - Descrição não pode ser vazia ou só espaços
      - Descrição deve ter no mínimo 3 caracteres
    - **Respostas:**
      - 200: Descrição atualizada com sucesso
      - 400: Descrição inválida
      - 404: Ambiente não encontrado
    """
    ambiente = ambiente_crud.atualizar_descricao_questionario(db, id_amb, payload.descricao_questionario)
    
    if not ambiente:
        exc = HTTPException(
            status_code=400,
            detail="Não foi possível atualizar a descrição. Verifique se a descrição é válida (mínimo 3 caracteres)."
        )
        exc.code = "invalid_descricao"
        raise exc
    
    nome_adm = ambiente.administrador.usuario.nome_completo if ambiente.administrador and ambiente.administrador.usuario else "(desconhecido)"
    ids_conjuntos = ambiente_crud.obter_conjuntos_do_ambiente(db, ambiente.id_amb)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="atualizar_descricao_questionario").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb}
        )
        db.add(log)
        db.commit()
    
    return AmbienteOut(
        id_amb=str(ambiente.id_amb),
        titulo_amb=ambiente.titulo_amb,
        titulo_questionario=ambiente.titulo_questionario,
        descricao_questionario=ambiente.descricao_questionario,
        data_criado=ambiente.data_criado,
        id_adm=str(ambiente.id_adm),
        nome_administrador=nome_adm,
        ativo=ambiente.ativo,
        ids_conjuntos=ids_conjuntos
    )


@router.patch("/{id_amb}/titulo-questionario", response_model=AmbienteOut, status_code=200)
def atualizar_titulo_questionario(
    id_amb: str,
    payload: AmbienteUpdateTituloQuestionario = Body(...),
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Atualiza o título do questionário de um ambiente.
    
    - **Acesso:** Apenas administradores autenticados.
    - **Validações:**
      - Se fornecido, título não pode ser só espaços
      - Título não pode exceder 255 caracteres
      - Pode ser None para remover o título
    - **Respostas:**
      - 200: Título atualizado com sucesso
      - 400: Título inválido
      - 404: Ambiente não encontrado
    """
    ambiente = ambiente_crud.atualizar_titulo_questionario(db, id_amb, payload.titulo_questionario)
    
    if not ambiente:
        exc = HTTPException(
            status_code=400,
            detail="Não foi possível atualizar o título do questionário. Verifique se o título é válido (máximo 255 caracteres)."
        )
        exc.code = "invalid_titulo_questionario"
        raise exc
    
    nome_adm = ambiente.administrador.usuario.nome_completo if ambiente.administrador and ambiente.administrador.usuario else "(desconhecido)"
    ids_conjuntos = ambiente_crud.obter_conjuntos_do_ambiente(db, ambiente.id_amb)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="atualizar_titulo_questionario").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb, "novo_titulo": payload.titulo_questionario}
        )
        db.add(log)
        db.commit()
    
    return AmbienteOut(
        id_amb=str(ambiente.id_amb),
        titulo_amb=ambiente.titulo_amb,
        titulo_questionario=ambiente.titulo_questionario,
        descricao_questionario=ambiente.descricao_questionario,
        data_criado=ambiente.data_criado,
        id_adm=str(ambiente.id_adm),
        nome_administrador=nome_adm,
        ativo=ambiente.ativo,
        ids_conjuntos=ids_conjuntos
    ) 