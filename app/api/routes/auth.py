from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import auth_service
from app.schemas import auth_schema
import logging
from app.schemas.auth_schema import CadastroPermitidoCreate
from app.crud import cadastro_permitido_crud
from app.services.auth_service import require_admin
from app.db import models
from fastapi import Body
from app.schemas.auth_schema import CadastroPermitidoOut
from app.schemas.auth_schema import UsuarioCreate
from app.core.utils import validar_cpf, validar_nome, validar_forca_senha
from app.crud.user_crud import get_user_by_email, get_user_by_cpf, create_usuario_convencional, create_usuario_administrador
from app.crud.cadastro_permitido_crud import get_cadastro_permitido_by_email, marcar_cadastro_como_usado
from datetime import datetime, timezone, timedelta
from app.schemas.auth_schema import UsuarioOut
from app.db.models import EventoAuditoria, LogAuditoria
from app.core.config import settings

# Configura logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

def _cookie_domain_or_none() -> str | None:
    """Retorna None se COOKIE_DOMAIN estiver vazio ou for a string 'None' (evita cookie inválido no Render)."""
    v = settings.COOKIE_DOMAIN
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("", "none"):
        return None
    return v


def set_auth_cookie(response: Response, access_token: str):
    """Define o cookie HttpOnly com o token de acesso. Usa settings para SameSite/Secure (produção cross-origin exige SameSite=none e Secure=true)."""
    samesite = (settings.COOKIE_SAMESITE or "lax").strip().lower()
    if samesite == "none" and not settings.COOKIE_SECURE:
        # Navegadores exigem Secure=True quando SameSite=None
        samesite = "lax"
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=settings.COOKIE_HTTPONLY,
        samesite=samesite,
        secure=settings.COOKIE_SECURE,
        path="/",
        domain=_cookie_domain_or_none(),
    )
    # Em desenvolvimento (HTTP, Secure=False): remover SameSite do header para cross-port localhost
    if not settings.COOKIE_SECURE:
        header = response.headers.get("set-cookie", "")
        if header:
            for attr in (f"; samesite={samesite}", f"; SameSite={samesite.capitalize()}"):
                header = header.replace(attr, "")
            response.headers["set-cookie"] = header

def clear_auth_cookie(response: Response):
    """Remove o cookie de autenticação."""
    response.delete_cookie(
        key="access_token",
        samesite=settings.COOKIE_SAMESITE or "lax",
        secure=settings.COOKIE_SECURE,
        domain=_cookie_domain_or_none(),
        path="/"
    )
    
   
@router.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Autentica o usuário e retorna um token de acesso JWT.
    ...
    """
    logger.info(f"Recebida tentativa de login para o usuário: {form_data.username}")
    user = auth_service.authenticate_user(db, email=form_data.username, password=form_data.password)
    if user == "inativo":
        logger.warning(f"Tentativa de login em conta desativada: {form_data.username}")
        exc = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta conta foi desativada. Entre em contato com o administrador do sistema."
        )
        exc.code = "inactive_account"
        raise exc
    if not user:
        logger.warning(f"Falha na autenticação para o usuário: {form_data.username}. Credenciais inválidas.")
        exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        exc.code = "invalid_credentials"
        raise exc
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id_usu)}, user=user
    )
    logger.info(f"Login bem-sucedido para o usuário: {form_data.username}")
    
    # Define o cookie HttpOnly
    set_auth_cookie(response, access_token)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="login").first()
    if evento:
        log = LogAuditoria(
            id_usu=user.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"email": user.email}
        )
        db.add(log)
        db.commit()
    
    # Retorna o token no JSON para compatibilidade (Swagger, testes, etc.)
    return {"access_token": access_token, "token_type": "bearer", "user_type": user.id_tipo}

@router.post("/cadastro", status_code=201, tags=["Autenticação"])
def cadastrar_usuario(
    response: Response,
    dados: UsuarioCreate,
    db: Session = Depends(get_db)
):
    """
    Cadastra um novo usuário (convencional ou administrador).
    Agora salva o telefone informado no formulário.
    """
    if get_user_by_email(db, dados.email):
        exc = HTTPException(status_code=400, detail="Email já cadastrado por outro usuário.")
        exc.code = "email_already_registered"
        raise exc
    if get_user_by_cpf(db, dados.cpf):
        exc = HTTPException(status_code=400, detail="CPF já cadastrado por outro usuário.")
        exc.code = "cpf_already_registered"
        raise exc
    cadastro = get_cadastro_permitido_by_email(db, dados.email)
    if not cadastro:
        exc = HTTPException(status_code=403, detail="Email não está autorizado para cadastro.")
        exc.code = "email_not_permitted"
        raise exc
    if cadastro.usado:
        exc = HTTPException(status_code=409, detail="Este email já foi utilizado para cadastro.")
        exc.code = "email_already_used"
        raise exc
    if cadastro.data_expiracao and cadastro.data_expiracao < datetime.now(timezone.utc):
        exc = HTTPException(status_code=410, detail="O cadastro permitido expirou.")
        exc.code = "cadastro_expired"
        raise exc
    if not validar_nome(dados.nome_completo):
        exc = HTTPException(status_code=422, detail="Nome completo inválido. Informe nome e sobrenome.")
        exc.code = "invalid_name"
        raise exc
    if not validar_cpf(dados.cpf):
        exc = HTTPException(status_code=422, detail="CPF inválido.")
        exc.code = "invalid_cpf"
        raise exc
    if not validar_forca_senha(dados.senha):
        exc = HTTPException(status_code=422, detail="Senha fraca. Use pelo menos 8 caracteres, incluindo maiúsculas, minúsculas e números.")
        exc.code = "weak_password"
        raise exc
    
    # Determinar tipo de usuário baseado no cadastro permitido
    tipo_usuario = db.query(models.TipoUsuario).filter(models.TipoUsuario.id_tipo == cadastro.id_tipo).first()
    if not tipo_usuario:
        exc = HTTPException(status_code=500, detail="Tipo de usuário não encontrado.")
        exc.code = "user_type_not_found"
        raise exc
    
    # Criar usuário baseado no tipo (AGORA PASSANDO O TELEFONE)
    if tipo_usuario.nome.lower() == "convencional":
        usuario = create_usuario_convencional(
            db=db, 
            nome_completo=dados.nome_completo, 
            email=dados.email, 
            senha=dados.senha, 
            cpf=dados.cpf, 
            id_tipo=tipo_usuario.id_tipo,
            telefone=dados.telefone  
        )
        evento_nome = "cadastrar_usuario_convencional"
    elif tipo_usuario.nome.lower() == "admin":
        usuario = create_usuario_administrador(
            db=db, 
            nome_completo=dados.nome_completo, 
            email=dados.email, 
            senha=dados.senha, 
            cpf=dados.cpf, 
            id_tipo=tipo_usuario.id_tipo,
            telefone=dados.telefone  
        )
        evento_nome = "cadastrar_usuario_administrador"
    else:
        exc = HTTPException(status_code=400, detail="Tipo de usuário inválido.")
        exc.code = "invalid_user_type"
        raise exc
    
    marcar_cadastro_como_usado(db, dados.email)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome=evento_nome).first()
    if evento:
        log = LogAuditoria(
            id_usu=usuario.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={
                "email": usuario.email, 
                "nome_completo": usuario.nome_completo, 
                "tipo": tipo_usuario.nome,
                "telefone": usuario.telefone
            }
        )
        db.add(log)
        db.commit()
    
    access_token = auth_service.create_access_token(data={"sub": str(usuario.id_usu)}, user=usuario)
    
    set_auth_cookie(response, access_token)
    
    return {"access_token": access_token, "token_type": "bearer", "user_type": usuario.id_tipo}
@router.post("/logout", status_code=200, tags=["Autenticação"])
def logout(response: Response, current_user: models.Usuario = Depends(auth_service.get_current_user), db: Session = Depends(get_db)):
    """
    Realiza logout do usuário, removendo o cookie de autenticação.
    ...
    """
    logger.info(f"Logout realizado para o usuário: {current_user.email}")
    
    # Remove o cookie HttpOnly
    clear_auth_cookie(response)
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="logout").first()
    if evento:
        log = LogAuditoria(
            id_usu=current_user.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"email": current_user.email}
        )
        db.add(log)
        db.commit()
    
    return {"message": "Logout realizado com sucesso"}