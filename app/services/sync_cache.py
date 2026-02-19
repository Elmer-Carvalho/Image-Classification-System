"""
Serviço para gerenciar cache de sincronização com NextCloud.
Usa a tabela SyncStatus como armazenamento persistente.
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
import logging
from app.db.models import SyncStatus
from app.core.timezone import local_to_utc, now as tz_now

logger = logging.getLogger(__name__)


class SyncCache:
    """Gerencia o cache de estado da sincronização."""
    
    def __init__(self, db: Session):
        """
        Inicializa o cache de sincronização.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self._ensure_sync_status_exists()
    
    def _ensure_sync_status_exists(self):
        """Garante que existe um registro SyncStatus (singleton)."""
        try:
            status = self.db.query(SyncStatus).filter_by(id=1).first()
            if not status:
                now = local_to_utc(tz_now())
                status = SyncStatus(
                    id=1,
                    activity_api_available=True,
                    activity_api_failures=0,
                    webdav_failures=0,
                    server_offline=False,
                    sync_in_progress=False,
                    created_at=now,
                    updated_at=now
                )
                self.db.add(status)
                self.db.commit()
                logger.info("Registro SyncStatus criado (singleton)")
        except IntegrityError:
            self.db.rollback()
            logger.warning("Tentativa de criar SyncStatus duplicado (ignorado)")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erro ao garantir SyncStatus: {e}")
            raise
    
    def get_sync_status(self) -> Optional[SyncStatus]:
        """
        Obtém o status atual da sincronização.
        
        Returns:
            Objeto SyncStatus ou None se não existir
        """
        return self.db.query(SyncStatus).filter_by(id=1).first()
    
    def update_last_activity_sync(self, timestamp):
        """Atualiza timestamp da última sincronização via Activity API."""
        status = self.get_sync_status()
        if status:
            status.last_activity_api_sync = timestamp
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def update_last_webdav_sync(self, timestamp):
        """Atualiza timestamp da última sincronização via WebDAV."""
        status = self.get_sync_status()
        if status:
            status.last_webdav_sync = timestamp
            status.updated_at = local_to_utc(tz_now())
            # Resetar contadores de falhas quando WebDAV sync acontece com sucesso
            status.activity_api_failures = 0
            status.webdav_failures = 0
            status.server_offline = False  # Servidor está online se WebDAV funcionou
            self.db.commit()
            logger.info("WebDAV sync concluída - contadores de falhas resetados")
    
    def set_activity_api_available(self, available: bool):
        """Marca disponibilidade da Activity API."""
        status = self.get_sync_status()
        if status:
            status.activity_api_available = available
            status.activity_api_last_check = local_to_utc(tz_now())
            if not available:
                status.activity_api_failures = 0  # Reset ao marcar como indisponível
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def increment_activity_api_failures(self):
        """Incrementa contador de falhas da Activity API."""
        status = self.get_sync_status()
        if status:
            status.activity_api_failures += 1
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
            
            # Se falhas >= 3, marcar como indisponível
            if status.activity_api_failures >= 3:
                status.activity_api_available = False
                self.db.commit()
                logger.warning(f"Activity API marcada como indisponível após {status.activity_api_failures} falhas")
    
    def reset_activity_api_failures(self):
        """Reseta contador de falhas da Activity API."""
        status = self.get_sync_status()
        if status:
            status.activity_api_failures = 0
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def increment_webdav_failures(self):
        """Incrementa contador de falhas do WebDAV."""
        status = self.get_sync_status()
        if status:
            status.webdav_failures += 1
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
            logger.warning(f"WebDAV falhou - contador: {status.webdav_failures}")
    
    def reset_webdav_failures(self):
        """Reseta contador de falhas do WebDAV."""
        status = self.get_sync_status()
        if status:
            status.webdav_failures = 0
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def set_server_offline(self, offline: bool):
        """Marca servidor como offline ou online."""
        status = self.get_sync_status()
        if status:
            status.server_offline = offline
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
            if offline:
                logger.warning("Servidor NextCloud marcado como OFFLINE")
            else:
                logger.info("Servidor NextCloud marcado como ONLINE")
    
    def update_health_check(self, timestamp):
        """Atualiza timestamp da última verificação de saúde do servidor."""
        status = self.get_sync_status()
        if status:
            status.last_health_check = timestamp
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def is_sync_in_progress(self) -> bool:
        """Verifica se há sincronização em progresso."""
        status = self.get_sync_status()
        return status.sync_in_progress if status else False
    
    def set_sync_in_progress(self, value: bool):
        """Marca sincronização como em progresso ou não."""
        status = self.get_sync_status()
        if status:
            status.sync_in_progress = value
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def set_webdav_initial_sync_start(self, timestamp):
        """Define timestamp de início da sincronização inicial WebDAV."""
        status = self.get_sync_status()
        if status:
            status.webdav_initial_sync_start = timestamp
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()
    
    def get_webdav_initial_sync_start(self):
        """Obtém timestamp de início da sincronização inicial WebDAV."""
        status = self.get_sync_status()
        return status.webdav_initial_sync_start if status else None
    
    def update_sync_result(self, status_str: str, method: str, error: Optional[str] = None):
        """
        Atualiza resultado da última sincronização.
        
        Args:
            status_str: 'success', 'error', ou 'partial'
            method: 'activity_api', 'webdav', ou 'initial'
            error: Mensagem de erro (se houver)
        """
        status = self.get_sync_status()
        if status:
            status.last_sync_status = status_str
            status.last_sync_method = method
            status.last_sync_error = error
            status.updated_at = local_to_utc(tz_now())
            self.db.commit()

