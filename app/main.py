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
from app.db.database import engine, get_db, SessionLocal, popular_eventos_auditoria, wait_for_database
from app.db.models import Base
from app.api.routes import auth
from app.api.routes import usuarios
from app.api.routes import whitelist
from app.api.routes import ambientes
from app.api.routes import usuarios_ambientes
from app.api.routes import auditoria
from app.api.routes import nextcloud_images
from app.api.routes import test_sync
# Removido: from app.services.image_service import ImageMonitor

# Criação de tabelas e dependências removidas conforme solicitado

# Variáveis globais
image_monitor = None
sync_scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global image_monitor, sync_scheduler
    
    # Aguardar banco de dados estar pronto
    print("🔄 Aguardando banco de dados estar pronto...")
    if not wait_for_database():
        print("❌ Falha ao conectar com o banco de dados. Encerrando aplicação.")
        raise Exception("Não foi possível conectar com o banco de dados")
    
    # Recriar banco de dados do zero (desenvolvimento)
    print("📊 Recriando banco de dados do zero...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Banco de dados recriado com sucesso!")

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
                cpf=settings.ADMIN_CPF,
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
        
        # Inicializar sincronização NextCloud
        from app.services.nextcloud_service import get_nextcloud_client
        from app.services.nextcloud_sync_service import NextCloudSyncService
        from app.services.sync_scheduler import SyncScheduler
        
        try:
            nextcloud_client = get_nextcloud_client()
            sync_service = NextCloudSyncService(get_db_session, nextcloud_client)
            
            # Sincronização inicial em background (se configurado)
            if settings.NEXTCLOUD_SYNC_INITIAL_ON_STARTUP:
                print(f"🔄 Sincronização inicial habilitada (NEXTCLOUD_SYNC_INITIAL_ON_STARTUP={settings.NEXTCLOUD_SYNC_INITIAL_ON_STARTUP})")
                def run_initial_sync():
                    """Executa sincronização inicial em background."""
                    try:
                        print("🔄 Iniciando sincronização inicial com NextCloud em background...")
                        result = sync_service.sync_initial()
                        if result.get('status') == 'success':
                            print("✅ Sincronização inicial concluída com sucesso")
                        else:
                            print(f"⚠️ Sincronização inicial concluída com avisos: {result.get('error', 'unknown')}")
                    except Exception as e:
                        print(f"❌ Erro na sincronização inicial: {e}")
                
                # Executar em thread separada para não bloquear o startup
                sync_thread = threading.Thread(
                    target=run_initial_sync,
                    name="NextCloud-Initial-Sync",
                    daemon=True
                )
                sync_thread.start()
                print("🔄 Sincronização inicial iniciada em background (servidor disponível)")
            else:
                print(f"⏭️ Sincronização inicial desabilitada (NEXTCLOUD_SYNC_INITIAL_ON_STARTUP={settings.NEXTCLOUD_SYNC_INITIAL_ON_STARTUP})")
            
            # Iniciar agendador de sincronização periódica
            sync_scheduler = SyncScheduler(sync_service)
            sync_scheduler.start()
            print("✅ Agendador de sincronização NextCloud iniciado")
            
        except Exception as e:
            print(f"⚠️ Erro ao inicializar sincronização NextCloud: {e}")
            print("   Sistema continuará sem sincronização automática")
        
    except Exception as e:
        print(f"Erro ao inicializar serviços: {e}")
    
    yield
    
    # Shutdown
    # Parar agendador de sincronização
    try:
        if sync_scheduler:
            sync_scheduler.stop()
            print("🛑 Agendador de sincronização NextCloud parado")
    except Exception as e:
        print(f"Erro ao parar agendador: {e}")

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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ],
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
app.include_router(nextcloud_images.router)
app.include_router(test_sync.router)

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