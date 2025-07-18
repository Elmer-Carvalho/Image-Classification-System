# Ponto de entrada da aplicação FastAPI 
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from sqlalchemy.orm import Session
import threading
import uvicorn
from contextlib import asynccontextmanager
import time
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.utils import hash_password
from app.db.database import engine, get_db, SessionLocal, popular_eventos_auditoria
from app.db.models import Base
from app.api.routes import auth
from app.api.routes import usuarios
from app.api.routes import whitelist
from app.api.routes import ambientes
from app.api.routes import usuarios_ambientes
from app.api.routes import auditoria
# Removido: from app.services.image_service import ImageMonitor

# Criação de tabelas e dependências removidas conforme solicitado

# Variável global para o monitor
image_monitor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global image_monitor
    
    # Criar tabelas no banco
    Base.metadata.create_all(bind=engine)

    # Popular eventos de auditoria após garantir que as tabelas existem
    from app.db.database import SessionLocal, popular_eventos_auditoria
    db = SessionLocal()
    try:
        popular_eventos_auditoria(db)
    finally:
        db.close()

    # Inserir tipos de usuário padrão se não existirem
    from app.db.database import SessionLocal
    from app.db.models import TipoUsuario, Usuario, UsuarioAdministrador
    session = SessionLocal()
    try:
        # Tipos de usuário
        if session.query(TipoUsuario).count() == 0:
            session.add_all([
                TipoUsuario(nome="convencional"),
                TipoUsuario(nome="admin")
            ])
            session.commit()
        # Admin inicial
        admin_tipo = session.query(TipoUsuario).filter_by(nome="admin").first()
        admin_exists = session.query(UsuarioAdministrador).count() > 0
        if not admin_exists and admin_tipo:
            from datetime import datetime
            import uuid
            admin_user = Usuario(
                id_usu=uuid.uuid4(),
                nome_completo=settings.ADMIN_NOME_COMPLETO,
                email=settings.ADMIN_EMAIL,
                senha_hash=hash_password(settings.ADMIN_SENHA),
                data_criado=datetime.now(),
                ativo=True,
                id_tipo=admin_tipo.id_tipo
            )
            session.add(admin_user)
            session.flush()  # Garante que o usuário tenha ID para FK
            admin_adm = UsuarioAdministrador(
                id_adm=uuid.uuid4(),
                id_usu=admin_user.id_usu
            )
            session.add(admin_adm)
            session.commit()
    except IntegrityError:
        session.rollback()
    finally:
        session.close()

    try:
        # Criar factory de sessão
        def get_db_session():
            return SessionLocal()
        
        # Inicializar monitor com polling a cada 3 segundos
        # Removido: image_monitor = ImageMonitor(get_db_session, check_interval=3)
        # Removido: image_monitor.start_monitoring()
        
        # logger.info("Sistema iniciado com monitoramento ativo") # Removido: logger
        print("Sistema iniciado (sem monitoramento de imagens)")
        
    except Exception as e:
        print(f"Erro ao inicializar monitoramento: {e}")
    
    yield
    
    # Shutdown
    # Removido: if image_monitor:
    # Removido:     image_monitor.stop_monitoring()

# Criar aplicação FastAPI
app = FastAPI(
    title="Sistema de Classificação de Imagens",
    description="API para processamento automático e visualização de imagens",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(whitelist.router)
app.include_router(ambientes.router)
app.include_router(usuarios_ambientes.router)
app.include_router(auditoria.router)

@app.get("/")
def read_root():
    # Removido: monitoring_status = "Ativo" if image_monitor and image_monitor.is_monitoring() else "Inativo"
    return {
        "message": "Sistema de Classificação de Imagens",
        "version": "1.0.0",
        "docs": "/docs",
        "monitoring": "Monitoramento de imagens desabilitado"
    }

@app.get("/health")
def health_check():
    # Removido: monitoring_status = image_monitor and image_monitor.is_monitoring()
    return {
        "status": "healthy", 
        "monitoring": False,
        "monitor_running": False
    }

@app.get("/monitor/status")
def monitor_status():
    """Endpoint para verificar status detalhado do monitoramento"""
    # Removido: if not image_monitor:
    return {"status": "Monitor não inicializado"}

@app.post("/monitor/restart")
def restart_monitor():
    """Reinicia o monitoramento"""
    global image_monitor
    
    # Removido: if image_monitor:
    # Removido:     image_monitor.stop_monitoring()
    # Removido:     time.sleep(1)
    # Removido:     image_monitor.start_monitoring()
    return {"message": "Monitoramento de imagens desabilitado"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = getattr(exc, "code", "http_exception")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": code,
            "status": exc.status_code
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Erro de validação nos dados enviados.",
            "code": "validation_error",
            "status": HTTP_422_UNPROCESSABLE_ENTITY,
            "errors": exc.errors()
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    ) 