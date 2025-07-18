from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin
from app.schemas.auth_schema import UsuarioConvencionalCreate, UsuarioAdministradorCreate, UsuarioOut
from app.core.utils import validar_cpf, validar_nome, validar_forca_senha
from app.crud.user_crud import get_user_by_email, get_user_by_cpf, create_usuario_convencional, create_usuario_administrador
from app.crud.cadastro_permitido_crud import get_cadastro_permitido_by_email, marcar_cadastro_como_usado
from app.db import models
from datetime import datetime, timezone

router = APIRouter(prefix="/usuarios", tags=["Gerenciar Usuários"])

# Remover as rotas de cadastro de usuário convencional e administrador deste arquivo

@router.get("/", response_model=list[UsuarioOut], tags=["Gerenciar Usuários"])
def listar_usuarios(
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos os usuários do sistema (convencionais e administradores).

    - **Acesso:** Apenas administradores autenticados.
    - **Resposta:** Lista de usuários com informações básicas, tipo, status e dados específicos.
    """
    usuarios = db.query(models.Usuario).all()
    result = []
    for u in usuarios:
        tipo = u.tipo.nome if u.tipo else "desconhecido"
        is_admin = u.tipo and u.tipo.nome.lower() == "admin"
        cpf = u.convencional.cpf if u.convencional else None
        crm = u.convencional.crm if u.convencional else None
        result.append(
            UsuarioOut(
                id_usu=str(u.id_usu),
                nome_completo=u.nome_completo,
                email=u.email,
                tipo=tipo,
                cpf=cpf,
                crm=crm,
                is_admin=is_admin,
                ativo=u.ativo
            )
        )
    return result

@router.delete("/{id_usu}", status_code=204, tags=["Gerenciar Usuários"])
def excluir_usuario(
    id_usu: str,
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Realiza a exclusão lógica (desativação) de um usuário pelo ID.

    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 204: Usuário desativado com sucesso
      - 404: Usuário não encontrado
      - 400/403: Erros de negócio
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usu == id_usu).first()
    if not usuario:
        exc = HTTPException(status_code=404, detail="Usuário não encontrado.")
        exc.code = "user_not_found"
        raise exc
    if not usuario.ativo:
        exc = HTTPException(status_code=400, detail="Usuário já está desativado.")
        exc.code = "user_already_inactive"
        raise exc
    if usuario.id_usu == admin.id_usu:
        exc = HTTPException(status_code=403, detail="Você não pode desativar a si mesmo.")
        exc.code = "cannot_deactivate_self"
        raise exc
    usuario.ativo = False
    db.commit()
    return

@router.patch("/{id_usu}/reativar", status_code=200, tags=["Gerenciar Usuários"])
def reativar_usuario(
    id_usu: str,
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reativa uma conta de usuário desativada.

    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 200: Usuário reativado com sucesso
      - 404: Usuário não encontrado
      - 400: Usuário já está ativo
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usu == id_usu).first()
    if not usuario:
        exc = HTTPException(status_code=404, detail="Usuário não encontrado.")
        exc.code = "user_not_found"
        raise exc
    if usuario.ativo:
        exc = HTTPException(status_code=400, detail="Usuário já está ativo.")
        exc.code = "user_already_active"
        raise exc
    usuario.ativo = True
    db.commit()
    return {"message": "Usuário reativado com sucesso."} 