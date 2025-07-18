from fastapi import APIRouter, Depends, HTTPException, status
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
from app.schemas.auth_schema import UsuarioConvencionalCreate, UsuarioAdministradorCreate
from app.core.utils import validar_cpf, validar_nome, validar_forca_senha
from app.crud.user_crud import get_user_by_email, get_user_by_cpf, create_usuario_convencional, create_usuario_administrador
from app.crud.cadastro_permitido_crud import get_cadastro_permitido_by_email, marcar_cadastro_como_usado
from datetime import datetime, timezone
from app.schemas.auth_schema import UsuarioOut
from app.db.models import EventoAuditoria, LogAuditoria

# Configura logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Autentica o usuário e retorna um token de acesso JWT.

    - **Payload:**
      - Formulário com campos `username` (email) e `password`.
    - **Respostas:**
      - 200: Login bem-sucedido (JWT retornado)
      - 401: Credenciais inválidas
      - 403: Conta desativada
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
        data={"sub": str(user.id_usu)}
    )
    logger.info(f"Login bem-sucedido para o usuário: {form_data.username}")
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
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/cadastro-convencional", status_code=201, tags=["Autenticação"])
def cadastrar_usuario_convencional(
    dados: UsuarioConvencionalCreate,
    db: Session = Depends(get_db)
):
    """
    Cadastra um novo usuário convencional.

    - **Regras:** O e-mail deve estar autorizado, não pode estar em uso, CPF deve ser único e válido.
    - **Payload de exemplo:**
      {
        "nome_completo": "João da Silva",
        "email": "joao.silva@email.com",
        "senha": "SenhaForte123",
        "cpf": "12345678901",
        "crm": "12345"
      }
    - **Respostas:**
      - 201: Usuário criado com sucesso (JWT retornado)
      - 400/403/409/422: Erros de validação ou negócio
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
    tipo_conv = db.query(models.TipoUsuario).filter(models.TipoUsuario.nome.ilike("convencional")).first()
    if not tipo_conv or cadastro.id_tipo != tipo_conv.id_tipo:
        exc = HTTPException(status_code=403, detail="O email não está autorizado para cadastro de usuário convencional.")
        exc.code = "wrong_user_type"
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
    usuario = create_usuario_convencional(db, dados.nome_completo, dados.email, dados.senha, dados.cpf, dados.crm, tipo_conv.id_tipo)
    marcar_cadastro_como_usado(db, dados.email)
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="cadastrar_usuario_convencional").first()
    if evento:
        log = LogAuditoria(
            id_usu=usuario.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"email": usuario.email, "nome_completo": usuario.nome_completo}
        )
        db.add(log)
        db.commit()
    access_token = auth_service.create_access_token(data={"sub": str(usuario.id_usu)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/cadastro-administrador", status_code=201, tags=["Autenticação"])
def cadastrar_usuario_administrador(
    dados: UsuarioAdministradorCreate,
    db: Session = Depends(get_db)
):
    """
    Cadastra um novo usuário administrador.

    - **Regras:** O e-mail deve estar autorizado, não pode estar em uso.
    - **Payload de exemplo:**
      {
        "nome_completo": "Maria Admin",
        "email": "maria.admin@email.com",
        "senha": "SenhaForte123"
      }
    - **Respostas:**
      - 201: Usuário criado com sucesso (JWT retornado)
      - 400/403/409/422: Erros de validação ou negócio
    """
    if get_user_by_email(db, dados.email):
        exc = HTTPException(status_code=400, detail="Email já cadastrado por outro usuário.")
        exc.code = "email_already_registered"
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
    tipo_adm = db.query(models.TipoUsuario).filter(models.TipoUsuario.nome.ilike("admin")).first()
    if not tipo_adm or cadastro.id_tipo != tipo_adm.id_tipo:
        exc = HTTPException(status_code=403, detail="O email não está autorizado para cadastro de administrador.")
        exc.code = "wrong_user_type"
        raise exc
    if cadastro.data_expiracao and cadastro.data_expiracao < datetime.now(timezone.utc):
        exc = HTTPException(status_code=410, detail="O cadastro permitido expirou.")
        exc.code = "cadastro_expired"
        raise exc
    if not validar_nome(dados.nome_completo):
        exc = HTTPException(status_code=422, detail="Nome completo inválido. Informe nome e sobrenome.")
        exc.code = "invalid_name"
        raise exc
    if not validar_forca_senha(dados.senha):
        exc = HTTPException(status_code=422, detail="Senha fraca. Use pelo menos 8 caracteres, incluindo maiúsculas, minúsculas e números.")
        exc.code = "weak_password"
        raise exc
    usuario = create_usuario_administrador(db, dados.nome_completo, dados.email, dados.senha, tipo_adm.id_tipo)
    marcar_cadastro_como_usado(db, dados.email)
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="cadastrar_usuario_administrador").first()
    if evento:
        log = LogAuditoria(
            id_usu=usuario.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"email": usuario.email, "nome_completo": usuario.nome_completo}
        )
        db.add(log)
        db.commit()
    access_token = auth_service.create_access_token(data={"sub": str(usuario.id_usu)})
    return {"access_token": access_token, "token_type": "bearer"} 