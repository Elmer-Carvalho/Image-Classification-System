"""
Serviço principal de sincronização híbrida com NextCloud.
Orquestra sincronização via Activity API e WebDAV (fallback).
"""
import threading
from datetime import timedelta
from typing import Callable, Dict, Optional
from sqlalchemy.orm import Session
import logging

from app.services.nextcloud_service import NextCloudClient
from app.services.activity_api_sync import ActivityAPISync
from app.services.webdav_sync import WebDAVSync
from app.services.sync_cache import SyncCache
from app.services.event_cache import EventCache
from app.core.config import settings
from app.core.timezone import local_to_utc, now as tz_now

logger = logging.getLogger(__name__)


class NextCloudSyncService:
    """Serviço principal de sincronização com NextCloud."""
    
    def __init__(self, db_session_factory: Callable[[], Session], nextcloud_client: NextCloudClient):
        """
        Inicializa serviço de sincronização.
        
        Args:
            db_session_factory: Função que retorna uma sessão do banco de dados
            nextcloud_client: Cliente NextCloud configurado
        """
        self.db_session_factory = db_session_factory
        self.client = nextcloud_client
        self.activity_api_sync = None
        self.webdav_sync = None
        self.sync_cache = None
    
    def _get_db_session(self) -> Session:
        """Obtém uma nova sessão do banco de dados."""
        return self.db_session_factory()
    
    def sync_initial(self) -> Dict[str, any]:
        """
        Sincronização inicial completa ao iniciar o sistema.
        
        Lógica:
        - Se banco está vazio: WebDAV faz varredura completa, Activity API coleta eventos em cache,
          depois eventos são aplicados quando WebDAV termina (evita race conditions).
        - Se banco tem dados: Apenas Activity API usando timestamp da última sincronização.
        
        Returns:
            Dicionário com estatísticas da sincronização
        """
        db = self._get_db_session()
        try:
            # Inicializar serviços
            self.sync_cache = SyncCache(db)
            
            # Verificar se já está sincronizando
            if self.sync_cache.is_sync_in_progress():
                logger.warning("⚠️ Sincronização já em progresso, aguardando...")
                return {'status': 'already_in_progress'}
            
            # Verificar se banco está vazio
            from app.db.models import ConjuntoImagens
            folder_count = db.query(ConjuntoImagens).count()
            is_empty = folder_count == 0
            
            if is_empty:
                logger.info("🚀 Banco vazio - Iniciando sincronização completa (WebDAV + Activity API)...")
                return self._sync_initial_empty_db(db)
            else:
                logger.info("🔄 Banco possui dados - Usando apenas Activity API...")
                return self._sync_initial_with_data(db)
        
        finally:
            db.close()
    
    def _sync_initial_empty_db(self, db: Session) -> Dict[str, any]:
        """
        Sincronização inicial quando banco está vazio.
        WebDAV faz varredura completa, Activity API coleta eventos em cache,
        depois eventos são aplicados sequencialmente.
        """
        # Variáveis temporárias para timestamps
        webdav_start_time = local_to_utc(tz_now())  # Timestamp de início do WebDAV
        webdav_end_time = None  # Timestamp de fim do WebDAV (será preenchido)
        last_activity_api_fetch_time = None  # Timestamp da última busca Activity API
        
        self.sync_cache.set_webdav_initial_sync_start(webdav_start_time)
        logger.info(f"📅 [WebDAV] Timestamp de início: {webdav_start_time.isoformat()}")
        
        # Cache para eventos do Activity API
        event_cache = EventCache()
        
        # Resultados
        webdav_result = {'status': 'pending'}
        activity_api_collect_result = {'status': 'pending'}
        events_apply_result = {'status': 'pending'}
        
        # Thread para WebDAV - faz varredura completa
        def run_webdav_sync():
            nonlocal webdav_result, webdav_end_time
            db_webdav = self._get_db_session()
            try:
                logger.info("🔄 [WebDAV] Iniciando varredura completa...")
                sync_cache_webdav = SyncCache(db_webdav)
                sync_cache_webdav.set_sync_in_progress(True)
                
                webdav_sync = WebDAVSync(self.client, db_webdav)
                stats = webdav_sync.sync_all_folders()
                
                webdav_end_time = local_to_utc(tz_now())
                sync_cache_webdav.update_last_webdav_sync(webdav_end_time)
                sync_cache_webdav.update_sync_result('success', 'initial')
                
                webdav_result = {'status': 'success', 'method': 'webdav', 'stats': stats, 'end_time': webdav_end_time}
                logger.info(f"✅ [WebDAV] Varredura concluída: {stats.get('folders_processed', 0)} pastas, {stats.get('images_processed', 0)} imagens")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ [WebDAV] Erro: {error_msg}")
                sync_cache_webdav = SyncCache(db_webdav)
                sync_cache_webdav.update_sync_result('error', 'initial', error_msg)
                webdav_result = {'status': 'error', 'error': error_msg}
            finally:
                db_webdav.close()
        
        # Thread para Activity API - coleta eventos em loop (evita duplicatas)
        def run_activity_api_collect():
            nonlocal activity_api_collect_result, last_activity_api_fetch_time
            db_activity = self._get_db_session()
            try:
                logger.info("🔄 [Activity API] Iniciando coleta de eventos...")
                
                # Verificar disponibilidade
                api_check = self.client.check_activity_api_available()
                if not api_check.get('available', False):
                    logger.warning(f"⚠️ [Activity API] Não disponível: {api_check.get('message', 'unknown')}")
                    activity_api_collect_result = {'status': 'api_unavailable', 'message': api_check.get('message')}
                    return
                
                activity_api_sync = ActivityAPISync(self.client, db_activity)
                total_events_collected = 0
                import time
                
                # Primeira busca: usa timestamp de início do WebDAV
                current_fetch_time = webdav_start_time
                
                # Primeira busca inicial
                events = activity_api_sync.fetch_events_since(current_fetch_time)
                if events:
                    current_fetch_time = local_to_utc(tz_now())
                    last_activity_api_fetch_time = current_fetch_time
                    event_cache.add_events(events, fetch_time=current_fetch_time)
                    total_events_collected += len(events)
                    logger.info(f"📦 [Activity API] Primeira busca: {len(events)} eventos coletados")
                else:
                    # Atualizar timestamp mesmo sem eventos
                    current_fetch_time = local_to_utc(tz_now())
                    last_activity_api_fetch_time = current_fetch_time
                    event_cache.set_last_fetch_time(current_fetch_time)
                    logger.info("📭 [Activity API] Primeira busca: nenhum evento encontrado")
                
                # Loop de buscas periódicas enquanto WebDAV está rodando
                max_iterations = 120  # Máximo de 10 minutos (120 * 5s)
                iteration = 0
                last_log_time = local_to_utc(tz_now())
                
                while webdav_result.get('status') == 'pending' and iteration < max_iterations:
                    time.sleep(5)  # Aguardar 5 segundos entre buscas
                    iteration += 1
                    
                    # Buscar eventos desde última busca
                    events = activity_api_sync.fetch_events_since(current_fetch_time)
                    
                    if events:
                        current_fetch_time = local_to_utc(tz_now())
                        last_activity_api_fetch_time = current_fetch_time
                        event_cache.add_events(events, fetch_time=current_fetch_time)
                        total_events_collected += len(events)
                        # Log sempre que houver eventos novos
                        logger.info(f"📦 [Activity API] Busca #{iteration}: +{len(events)} eventos (total: {total_events_collected})")
                    else:
                        # Atualizar timestamp mesmo sem eventos para evitar buscar eventos antigos
                        current_fetch_time = local_to_utc(tz_now())
                        last_activity_api_fetch_time = current_fetch_time
                        event_cache.set_last_fetch_time(current_fetch_time)
                        
                        # Log periódico a cada 12 iterações (1 minuto) para mostrar que está ativo
                        if iteration % 12 == 0:
                            elapsed_minutes = iteration * 5 / 60
                            logger.info(f"🔄 [Activity API] Monitorando... ({elapsed_minutes:.1f}min, {total_events_collected} eventos coletados até agora)")
                
                # Uma última busca após WebDAV terminar (para pegar eventos que podem ter ocorrido durante)
                if webdav_result.get('status') == 'success':
                    final_fetch_time = last_activity_api_fetch_time if last_activity_api_fetch_time else webdav_start_time
                    final_events = activity_api_sync.fetch_events_since(final_fetch_time)
                    
                    if final_events:
                        final_fetch_timestamp = local_to_utc(tz_now())
                        last_activity_api_fetch_time = final_fetch_timestamp
                        event_cache.add_events(final_events, fetch_time=final_fetch_timestamp)
                        total_events_collected += len(final_events)
                        logger.info(f"📦 [Activity API] Busca final: {len(final_events)} eventos coletados")
                
                if total_events_collected > 0:
                    activity_api_collect_result = {'status': 'success', 'events_collected': total_events_collected, 'last_fetch_time': last_activity_api_fetch_time}
                    logger.info(f"📦 [Activity API] Total: {total_events_collected} eventos coletados e armazenados em cache")
                else:
                    activity_api_collect_result = {'status': 'success', 'events_collected': 0}
                    logger.info("📭 [Activity API] Nenhum evento encontrado")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ [Activity API] Erro ao coletar eventos: {error_msg}")
                activity_api_collect_result = {'status': 'error', 'error': error_msg}
            finally:
                db_activity.close()
        
        # Iniciar threads
        webdav_thread = threading.Thread(
            target=run_webdav_sync,
            name="NextCloud-Initial-WebDAV",
            daemon=True
        )
        activity_thread = threading.Thread(
            target=run_activity_api_collect,
            name="NextCloud-Initial-ActivityAPI-Collect",
            daemon=True
        )
        
        webdav_thread.start()
        activity_thread.start()
        
        # Aguardar conclusão
        webdav_thread.join()
        activity_thread.join()
        
        # Se WebDAV teve sucesso e há eventos no cache, aplicar eventos agora
        if webdav_result.get('status') == 'success' and not event_cache.is_empty():
            logger.info(f"📥 Aplicando {event_cache.count()} eventos coletados pelo Activity API...")
            events_apply_result = self._apply_cached_events(event_cache)
        else:
            events_apply_result = {'status': 'skipped', 'reason': 'no_events' if event_cache.is_empty() else 'webdav_failed'}
        
        # Atualizar timestamps finais no banco de dados
        if webdav_result.get('status') == 'success':
            sync_cache_final = SyncCache(self._get_db_session())
            sync_cache_final.set_sync_in_progress(False)
            
            # Decidir qual timestamp salvar baseado no que aconteceu
            if event_cache.is_empty() or events_apply_result.get('status') != 'success':
                # Activity API não captou eventos ou falhou ao aplicar: usar timestamp do final do WebDAV
                final_timestamp = webdav_end_time
                sync_cache_final.update_last_webdav_sync(final_timestamp)
                logger.info(f"💾 [Sync] Timestamp salvo: final do WebDAV ({final_timestamp.isoformat()})")
            else:
                # Activity API captou e aplicou eventos: usar timestamp do último processo Activity API
                final_timestamp = last_activity_api_fetch_time if last_activity_api_fetch_time else local_to_utc(tz_now())
                sync_cache_final.update_last_activity_api_sync(final_timestamp)
                sync_cache_final.reset_activity_api_failures()
                logger.info(f"💾 [Sync] Timestamp salvo: último Activity API ({final_timestamp.isoformat()})")
        
        return {
            'status': 'success',
            'webdav': webdav_result,
            'activity_api_collect': activity_api_collect_result,
            'events_apply': events_apply_result
        }
    
    def _sync_initial_with_data(self, db: Session) -> Dict[str, any]:
        """
        Sincronização quando banco já possui dados.
        Usa apenas Activity API com timestamp da última sincronização.
        """
        return self._sync_via_activity_api(db)
    
    def _apply_cached_events(self, event_cache: EventCache) -> Dict[str, any]:
        """
        Aplica eventos do cache ao banco de dados.
        Executado após WebDAV terminar para evitar race conditions.
        """
        db = self._get_db_session()
        try:
            events = event_cache.get_events()
            if not events:
                return {'status': 'success', 'events_applied': 0}
            
            logger.info(f"📥 Aplicando {len(events)} eventos do cache...")
            activity_api_sync = ActivityAPISync(self.client, db)
            stats = activity_api_sync.process_events(events)
            
            # Atualizar cache
            now_utc = local_to_utc(tz_now())
            sync_cache = SyncCache(db)
            sync_cache.update_last_activity_api_sync(now_utc)
            sync_cache.reset_activity_api_failures()
            
            logger.info(f"✅ Eventos aplicados: {stats}")
            return {'status': 'success', 'stats': stats}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Erro ao aplicar eventos do cache: {error_msg}")
            return {'status': 'error', 'error': error_msg}
        finally:
            db.close()
    
    def sync_periodic(self) -> Dict[str, any]:
        """
        Sincronização periódica (rota principal).
        Decide entre Activity API ou WebDAV baseado no cache.
        
        Returns:
            Dicionário com resultado da sincronização
        """
        db = self._get_db_session()
        try:
            # Inicializar serviços
            self.sync_cache = SyncCache(db)
            
            # Verificar se já está sincronizando
            if self.sync_cache.is_sync_in_progress():
                logger.debug("Sincronização já em progresso, pulando...")
                return {'status': 'already_in_progress'}
            
            # Decidir método de sincronização
            should_use_webdav = self._should_use_webdav()
            
            if should_use_webdav:
                return self._sync_via_webdav(db)
            else:
                return self._sync_via_activity_api(db)
        
        finally:
            db.close()
    
    def _should_use_webdav(self) -> bool:
        """
        Decide se deve usar WebDAV (fallback) ou Activity API.
        
        Returns:
            True se deve usar WebDAV, False para Activity API
        """
        status = self.sync_cache.get_sync_status()
        if not status:
            return True  # Se não há status, usar WebDAV
        
        # Se Activity API não está disponível, usar WebDAV
        if not status.activity_api_available:
            # Verificar se já passou tempo suficiente desde última sync WebDAV
            if status.last_webdav_sync:
                last_webdav = status.last_webdav_sync
                interval_minutes = settings.NEXTCLOUD_SYNC_WEBDAV_INTERVAL
                if local_to_utc(tz_now()) - last_webdav < timedelta(minutes=interval_minutes):
                    return False  # Ainda não é hora de sync WebDAV
            return True
        
        # Se Activity API está disponível, verificar última sync
        if status.last_activity_api_sync:
            last_activity = status.last_activity_api_sync
            interval_minutes = settings.NEXTCLOUD_SYNC_ACTIVITY_API_INTERVAL
            if local_to_utc(tz_now()) - last_activity < timedelta(minutes=interval_minutes):
                return False  # Ainda não é hora de sync Activity API
        
        return False  # Usar Activity API
    
    def _sync_via_activity_api(self, db: Session) -> Dict[str, any]:
        """
        Sincronização via Activity API.
        
        Args:
            db: Sessão do banco de dados
            
        Returns:
            Dicionário com resultado
        """
        try:
            logger.info("🔄 [Activity API] Iniciando sincronização...")
            
            # Inicializar serviços
            self.activity_api_sync = ActivityAPISync(self.client, db)
            
            # Marcar como em progresso
            self.sync_cache.set_sync_in_progress(True)
            
            try:
                # Verificar disponibilidade da Activity API
                logger.debug("🔍 [Activity API] Verificando disponibilidade...")
                api_check = self.client.check_activity_api_available()
                
                if not api_check.get('available', False):
                    logger.warning(f"⚠️ [Activity API] Não disponível: {api_check.get('message', 'unknown')}")
                    self.sync_cache.set_activity_api_available(False)
                    self.sync_cache.increment_activity_api_failures()
                    return {'status': 'api_unavailable', 'message': api_check.get('message')}
                
                logger.info("✅ [Activity API] API disponível")
                
                # Buscar timestamp da última sync
                status = self.sync_cache.get_sync_status()
                since_timestamp = status.last_activity_api_sync if status else None
                
                # Se não há última sync, verificar se há timestamp de início do WebDAV (durante inicialização)
                if not since_timestamp:
                    webdav_start = self.sync_cache.get_webdav_initial_sync_start()
                    if webdav_start:
                        since_timestamp = webdav_start
                        logger.info(f"📅 [Activity API] Usando timestamp de início do WebDAV: {since_timestamp.isoformat()}")
                
                if since_timestamp:
                    logger.info(f"📅 [Activity API] Buscando eventos desde: {since_timestamp.isoformat()}")
                else:
                    logger.info("📅 [Activity API] Buscando todos os eventos (primeira sincronização)")
                
                # Buscar eventos
                events = self.activity_api_sync.fetch_events_since(since_timestamp)
                
                if not events:
                    logger.info("📭 [Activity API] Nenhum evento novo encontrado")
                    now = local_to_utc(tz_now())
                    self.sync_cache.update_last_activity_sync(now)
                    self.sync_cache.reset_activity_api_failures()
                    return {'status': 'success', 'method': 'activity_api', 'events': 0}
                
                # Processar eventos
                stats = self.activity_api_sync.process_events(events)
                
                # Atualizar cache
                now = local_to_utc(tz_now())
                self.sync_cache.update_last_activity_sync(now)
                self.sync_cache.reset_activity_api_failures()
                self.sync_cache.update_sync_result('success', 'activity_api')
                
                logger.info(f"✅ [Activity API] Sincronização concluída: {stats['events_processed']} eventos processados, "
                           f"{stats['images_created']} criadas, {stats['images_updated']} atualizadas, "
                           f"{stats['images_deleted']} deletadas")
                return {'status': 'success', 'method': 'activity_api', 'stats': stats}
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Erro na sincronização Activity API: {error_msg}")
                self.sync_cache.increment_activity_api_failures()
                self.sync_cache.update_sync_result('error', 'activity_api', error_msg)
                
                # Verificar se servidor está completamente offline
                self._check_server_offline_status()
                
                return {'status': 'error', 'method': 'activity_api', 'error': error_msg}
            
            finally:
                self.sync_cache.set_sync_in_progress(False)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro crítico na sincronização Activity API: {error_msg}")
            return {'status': 'error', 'error': error_msg}
    
    def _sync_via_webdav(self, db: Session) -> Dict[str, any]:
        """
        Sincronização via WebDAV (fallback).
        
        Args:
            db: Sessão do banco de dados
        
        Returns:
            Dicionário com resultado
        """
        try:
            logger.info("🔄 [WebDAV] Iniciando sincronização completa (fallback)...")
            
            # Inicializar serviços
            self.webdav_sync = WebDAVSync(self.client, db)
            
            # Marcar como em progresso
            self.sync_cache.set_sync_in_progress(True)
            
            try:
                # Executar sincronização completa
                stats = self.webdav_sync.sync_all_folders()
                
                # Atualizar cache
                now = local_to_utc(tz_now())
                self.sync_cache.update_last_webdav_sync(now)
                self.sync_cache.update_sync_result('success', 'webdav')
                self.sync_cache.reset_webdav_failures()
                self.sync_cache.set_server_offline(False)  # Servidor está online
                
                # Resetar falhas da Activity API (pode ter sido reativada)
                self.sync_cache.reset_activity_api_failures()
                
                # Verificar se Activity API voltou a funcionar
                api_check = self.client.check_activity_api_available()
                if api_check.get('available', False):
                    self.sync_cache.set_activity_api_available(True)
                    logger.info("✅ [WebDAV] Activity API detectada como disponível novamente")
                
                logger.info(f"✅ [WebDAV] Sincronização concluída: {stats.get('folders_processed', 0)} pastas, "
                           f"{stats.get('images_processed', 0)} imagens processadas")
                return {'status': 'success', 'method': 'webdav', 'stats': stats}
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Erro na sincronização WebDAV: {error_msg}")
                self.sync_cache.increment_webdav_failures()
                self.sync_cache.update_sync_result('error', 'webdav', error_msg)
                
                # Verificar se servidor está completamente offline
                self._check_server_offline_status()
                
                return {'status': 'error', 'method': 'webdav', 'error': error_msg}
            
            finally:
                self.sync_cache.set_sync_in_progress(False)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro crítico na sincronização WebDAV: {error_msg}")
            self.sync_cache.increment_webdav_failures()
            self._check_server_offline_status()
            return {'status': 'error', 'error': error_msg}
    
    def _check_server_offline_status(self):
        """
        Verifica se o servidor está completamente offline e atualiza status.
        Servidor é considerado offline quando ambos Activity API e WebDAV falharam.
        """
        status = self.sync_cache.get_sync_status()
        if not status:
            return
        
        # Se ambos têm falhas consecutivas >= 3, servidor está offline
        activity_failed = not status.activity_api_available and status.activity_api_failures >= 3
        webdav_failed = status.webdav_failures >= 3
        
        if activity_failed and webdav_failed:
            self.sync_cache.set_server_offline(True)
            logger.warning("⚠️ Servidor NextCloud detectado como OFFLINE (ambos métodos falhando)")
        else:
            # Se pelo menos um método funciona, servidor está online
            self.sync_cache.set_server_offline(False)
    
    def get_sync_status(self) -> Dict[str, any]:
        """
        Obtém status atual da sincronização.
        
        Returns:
            Dicionário com informações de status
        """
        db = self._get_db_session()
        try:
            cache = SyncCache(db)
            status = cache.get_sync_status()
            
            if not status:
                return {'status': 'not_initialized'}
            
            return {
                'sync_in_progress': status.sync_in_progress,
                'activity_api_available': status.activity_api_available,
                'activity_api_failures': status.activity_api_failures,
                'webdav_failures': status.webdav_failures,
                'server_offline': status.server_offline,
                'last_health_check': status.last_health_check.isoformat() if status.last_health_check else None,
                'last_activity_api_sync': status.last_activity_api_sync.isoformat() if status.last_activity_api_sync else None,
                'last_webdav_sync': status.last_webdav_sync.isoformat() if status.last_webdav_sync else None,
                'last_sync_status': status.last_sync_status,
                'last_sync_method': status.last_sync_method,
                'last_sync_error': status.last_sync_error
            }
        
        finally:
            db.close()

