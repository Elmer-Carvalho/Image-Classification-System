from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin
from app.schemas.auth_schema import UsuarioOut
from app.core.utils import validar_cpf, validar_nome, validar_forca_senha
from app.crud.user_crud import get_user_by_email, get_user_by_cpf, create_usuario_convencional, create_usuario_administrador
from app.crud.cadastro_permitido_crud import get_cadastro_permitido_by_email, marcar_cadastro_como_usado
from app.services.auth_service import get_current_user, verify_password, get_password_hash
from app.schemas.auth_schema import UsuarioUpdatePerfil, UsuarioUpdateSenha
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
    Lista todos os usuários do sistema.
    ATUALIZADO: Agora retorna id_con se for especialista.
    """
    usuarios = db.query(models.Usuario).all()
    result = []
    for u in usuarios:
        tipo = u.tipo.nome if u.tipo else "desconhecido"
        is_admin = u.tipo and u.tipo.nome.lower() == "admin"
        
        cpf = None
        id_con = None  # <--- Variável nova
        
        # Lógica para capturar IDs específicos
        if u.convencional:
            cpf = u.convencional.cpf
            id_con = str(u.convencional.id_con) # <--- PEGA O ID DO MÉDICO
        elif u.administrador:
            cpf = u.administrador.cpf
            
        result.append(
            UsuarioOut(
                id_usu=str(u.id_usu),
                id_con=id_con,          # <--- PREENCHE NO JSON
                nome_completo=u.nome_completo,
                email=u.email,
                telefone=u.telefone,
                tipo=tipo,
                cpf=cpf,
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


# --- ROTAS DE "MINHA CONTA" ---

@router.get("/me", response_model=UsuarioOut)
def ler_meus_dados(
    current_user: models.Usuario = Depends(get_current_user)
):
    """Retorna os dados do usuário logado."""
    tipo = current_user.tipo.nome if current_user.tipo else "desconhecido"
    is_admin = current_user.tipo and current_user.tipo.nome.lower() == "admin"
    
    cpf = None
    if current_user.convencional:
        cpf = current_user.convencional.cpf
    elif current_user.administrador:
        cpf = current_user.administrador.cpf

    return UsuarioOut(
        id_usu=str(current_user.id_usu),
        nome_completo=current_user.nome_completo,
        email=current_user.email,
        telefone=current_user.telefone, # Agora retornamos o telefone
        tipo=tipo,
        cpf=cpf,
        is_admin=is_admin,
        ativo=current_user.ativo
    )

@router.patch("/me", response_model=UsuarioOut)
def atualizar_meu_perfil(
    dados: UsuarioUpdatePerfil,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Atualiza nome, email ou telefone."""
    if dados.nome_completo:
        current_user.nome_completo = dados.nome_completo
    if dados.telefone:
        current_user.telefone = dados.telefone
    if dados.email:
        # Verifica se o email já está em uso por OUTRA pessoa
        existente = db.query(models.Usuario).filter(models.Usuario.email == dados.email).first()
        if existente and existente.id_usu != current_user.id_usu:
            raise HTTPException(status_code=400, detail="Este e-mail já está em uso.")
        current_user.email = dados.email
    
    db.commit()
    db.refresh(current_user)
    
    # Reutiliza a lógica de retorno (copie a lógica do 'cpf' e 'tipo' do GET acima)
    tipo = current_user.tipo.nome if current_user.tipo else "desconhecido"
    is_admin = current_user.tipo and current_user.tipo.nome.lower() == "admin"
    cpf = current_user.convencional.cpf if current_user.convencional else (current_user.administrador.cpf if current_user.administrador else None)

    return UsuarioOut(
        id_usu=str(current_user.id_usu),
        nome_completo=current_user.nome_completo,
        email=current_user.email,
        telefone=current_user.telefone,
        tipo=tipo,
        cpf=cpf,
        is_admin=is_admin,
        ativo=current_user.ativo
    )

@router.patch("/me/senha", status_code=200)
def alterar_minha_senha(
    dados: UsuarioUpdateSenha,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Verifica a senha atual e define uma nova."""
    # 1. Verificar senha antiga
    if not verify_password(dados.senha_atual, current_user.senha_hash):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    
    # 2. Salvar nova senha
    current_user.senha_hash = get_password_hash(dados.nova_senha)
    db.commit()
    
    return {"message": "Senha alterada com sucesso!"}