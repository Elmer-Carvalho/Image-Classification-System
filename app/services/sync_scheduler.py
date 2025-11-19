"""
Agendador de tarefas de sincronização periódica com NextCloud.
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.services.nextcloud_sync_service import NextCloudSyncService
from app.core.config import settings
from app.core.timezone import local_to_utc, now as tz_now

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Agendador de sincronização periódica."""
    
    def __init__(self, sync_service: NextCloudSyncService):
        """
        Inicializa agendador.
        
        Args:
            sync_service: Serviço de sincronização
        """
        self.sync_service = sync_service
        self.activity_thread: Optional[threading.Thread] = None
        self.webdav_thread: Optional[threading.Thread] = None
        self.running = False
        self.stop_event = threading.Event()
    
    def start(self):
        """Inicia agendamento de sincronizações."""
        if self.running:
            logger.warning("Agendador já está em execução")
            return
        
        self.running = True
        self.stop_event.clear()
        
        # Iniciar thread de sincronização Activity API
        self.activity_thread = threading.Thread(
            target=self._activity_sync_loop,
            name="NextCloud-ActivityAPI-Sync",
            daemon=True
        )
        self.activity_thread.start()
        
        # Iniciar thread de sincronização WebDAV
        self.webdav_thread = threading.Thread(
            target=self._webdav_sync_loop,
            name="NextCloud-WebDAV-Sync",
            daemon=True
        )
        self.webdav_thread.start()
        
        logger.info("Agendador de sincronização iniciado")
    
    def stop(self):
        """Para agendamento de sincronizações."""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        # Aguardar threads terminarem (com timeout)
        if self.activity_thread:
            self.activity_thread.join(timeout=5)
        if self.webdav_thread:
            self.webdav_thread.join(timeout=5)
        
        logger.info("Agendador de sincronização parado")
    
    def _activity_sync_loop(self):
        """Loop de sincronização via Activity API."""
        interval_minutes = settings.NEXTCLOUD_SYNC_ACTIVITY_API_INTERVAL
        interval_seconds = interval_minutes * 60
        
        logger.info(f"🔄 [Scheduler] Activity API iniciado: intervalo de {interval_minutes} minuto(s)")
        logger.info(f"📋 [Scheduler] Configuração lida do .env: NEXTCLOUD_SYNC_ACTIVITY_API_INTERVAL={interval_minutes}")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Verificar se deve executar sync Activity API
                status = self.sync_service.get_sync_status()
                
                if status.get('activity_api_available', False):
                    # Verificar se já passou tempo suficiente desde a última sync
                    last_sync = status.get('last_activity_api_sync')
                    should_execute = True
                    
                    if last_sync:
                        try:
                            last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                            time_since = local_to_utc(tz_now()) - last_sync_dt
                            time_since_minutes = time_since.total_seconds() / 60
                            
                            if time_since_minutes < interval_minutes:
                                # Ainda não é hora, aguardar
                                wait_seconds = (interval_minutes - time_since_minutes) * 60
                                logger.debug(f"⏳ [Scheduler] Activity API: aguardando {wait_seconds:.0f}s (última sync há {time_since_minutes:.1f} min)")
                                if wait_seconds > 0:
                                    self.stop_event.wait(min(wait_seconds, interval_seconds))
                                should_execute = False
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"⚠️ [Scheduler] Erro ao parsear timestamp da última sync Activity API: {e}")
                            # Continuar e executar
                            should_execute = True
                    
                    if should_execute:
                        # Executar sincronização
                        current_time = tz_now().strftime('%H:%M:%S')
                        logger.info(f"🔄 [Scheduler] [{current_time}] Executando sincronização Activity API...")
                        result = self.sync_service.sync_periodic()
                        status_result = result.get('status', 'unknown')
                        if status_result == 'success':
                            stats = result.get('stats', {})
                            events = stats.get('events_processed', 0)
                            folders_created = stats.get('folders_created', 0)
                            folders_deleted = stats.get('folders_deleted', 0)
                            images_created = stats.get('images_created', 0)
                            images_deleted = stats.get('images_deleted', 0)
                            
                            if events > 0:
                                changes = []
                                if folders_created > 0:
                                    changes.append(f"{folders_created} pasta(s) criada(s)")
                                if folders_deleted > 0:
                                    changes.append(f"{folders_deleted} pasta(s) removida(s)")
                                if images_created > 0:
                                    changes.append(f"{images_created} imagem(ns) criada(s)")
                                if images_deleted > 0:
                                    changes.append(f"{images_deleted} imagem(ns) removida(s)")
                                
                                changes_str = ", ".join(changes) if changes else "sem mudanças"
                                logger.info(f"✅ [Scheduler] [{current_time}] Activity API: {events} eventos processados ({changes_str})")
                            else:
                                logger.info(f"✅ [Scheduler] [{current_time}] Activity API: nenhum evento novo")
                        else:
                            logger.warning(f"⚠️ [Scheduler] [{current_time}] Activity API concluída: {status_result}")
                
                # Aguardar próximo ciclo
                logger.debug(f"⏳ [Scheduler] Activity API: aguardando {interval_seconds}s até próxima verificação...")
                self.stop_event.wait(interval_seconds)
            
            except Exception as e:
                logger.error(f"❌ [Scheduler] Erro no loop de sincronização Activity API: {e}")
                # Aguardar antes de tentar novamente
                self.stop_event.wait(interval_seconds)
    
    def _webdav_sync_loop(self):
        """Loop de sincronização via WebDAV (fallback)."""
        interval_minutes = settings.NEXTCLOUD_SYNC_WEBDAV_INTERVAL
        interval_seconds = interval_minutes * 60
        interval_hours = interval_minutes / 60
        
        logger.info(f"🔄 [Scheduler] WebDAV iniciado: intervalo de {interval_minutes} minutos ({interval_hours:.1f} horas)")
        logger.info(f"📋 [Scheduler] Configuração lida do .env: NEXTCLOUD_SYNC_WEBDAV_INTERVAL={interval_minutes}")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Verificar se Activity API está indisponível
                status = self.sync_service.get_sync_status()
                
                if not status.get('activity_api_available', False):
                    # Verificar se já passou tempo suficiente desde última sync WebDAV
                    last_sync = status.get('last_webdav_sync')
                    should_execute = True
                    
                    if last_sync:
                        try:
                            last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                            time_since = local_to_utc(tz_now()) - last_sync_dt
                            time_since_minutes = time_since.total_seconds() / 60
                            
                            if time_since_minutes < interval_minutes:
                                # Ainda não é hora, aguardar
                                wait_seconds = (interval_minutes - time_since_minutes) * 60
                                wait_hours = wait_seconds / 3600
                                logger.debug(f"⏳ [Scheduler] WebDAV: aguardando {wait_hours:.1f}h (última sync há {time_since_minutes/60:.1f}h)")
                                if wait_seconds > 0:
                                    self.stop_event.wait(min(wait_seconds, interval_seconds))
                                should_execute = False
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"⚠️ [Scheduler] Erro ao parsear timestamp da última sync WebDAV: {e}")
                            # Continuar e executar
                            should_execute = True
                    
                    if should_execute:
                        # Executar sincronização WebDAV
                        current_time = tz_now().strftime('%H:%M:%S')
                        logger.info(f"⏰ [Scheduler] [{current_time}] Executando sincronização WebDAV (Activity API indisponível)...")
                        result = self.sync_service.sync_periodic()
                        status_result = result.get('status', 'unknown')
                        logger.info(f"✅ [Scheduler] [{current_time}] WebDAV concluída: {status_result}")
                else:
                    logger.debug(f"⏳ [Scheduler] WebDAV: Activity API disponível, aguardando {interval_seconds}s...")
                
                # Aguardar próximo ciclo
                self.stop_event.wait(interval_seconds)
            
            except Exception as e:
                logger.error(f"❌ [Scheduler] Erro no loop de sincronização WebDAV: {e}")
                # Aguardar antes de tentar novamente
                self.stop_event.wait(interval_seconds)

