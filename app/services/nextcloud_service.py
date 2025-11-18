"""
Serviço para integração com NextCloud via WebDAV.
Responsável por listar pastas, filtrar imagens e fazer download de arquivos.
"""
import requests
from requests.auth import HTTPBasicAuth
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET
from datetime import datetime
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class NextCloudClient:
    """Cliente WebDAV para interagir com NextCloud."""
    
    def __init__(self):
        """Inicializa o cliente com credenciais do settings."""
        # Lê configurações diretamente do settings (pydantic-settings já trata comentários)
        base_url = settings.NEXTCLOUD_BASE_URL.strip() if settings.NEXTCLOUD_BASE_URL else ""
        username = settings.NEXTCLOUD_USERNAME.strip() if settings.NEXTCLOUD_USERNAME else ""
        password = settings.NEXTCLOUD_PASSWORD.strip() if settings.NEXTCLOUD_PASSWORD else ""
        user_path = settings.NEXTCLOUD_USER_PATH.strip() if settings.NEXTCLOUD_USER_PATH else ""
        webdav_path = (settings.NEXTCLOUD_WEBDAV_PATH or "/remote.php/dav").strip()
        
        # Validação de configurações obrigatórias
        if not base_url:
            raise ValueError(
                "NEXTCLOUD_BASE_URL não configurado. "
                "Configure no arquivo .env (ex: https://cloud.example.com)"
            )
        if not username:
            raise ValueError(
                "NEXTCLOUD_USERNAME não configurado. "
                "Configure no arquivo .env"
            )
        if not password:
            raise ValueError(
                "NEXTCLOUD_PASSWORD não configurado. "
                "Configure no arquivo .env"
            )
        if not user_path:
            raise ValueError(
                "NEXTCLOUD_USER_PATH não configurado. "
                "Configure no arquivo .env (ex: /files/username)"
            )
        
        # Remove barra final da base_url (se houver)
        self.base_url = base_url.rstrip('/')
        # Remove barra final do webdav_path (se houver)
        self.webdav_path = webdav_path.rstrip('/')
        # Remove barra final do user_path (se houver)
        self.user_path = user_path.rstrip('/')
        self.username = username
        self.password = password
        
        # Validação de formato da URL base
        if not self.base_url.startswith(('http://', 'https://')):
            raise ValueError(
                f"NEXTCLOUD_BASE_URL deve começar com http:// ou https://. "
                f"Valor atual: '{base_url}'"
            )
        
        # Constrói URL base do WebDAV: base_url + webdav_path
        # Exemplo: https://example.com + /remote.php/dav = https://example.com/remote.php/dav
        self.webdav_base_url = f"{self.base_url}{self.webdav_path}"
        
        # Log para debug (sem expor senha)
        logger.info(f"NextCloud configurado - Base URL: {self.base_url}, User: {self.username}, User Path: {self.user_path}")
        logger.debug(f"WebDAV Base URL: {self.webdav_base_url}")
        
        # Namespaces XML do WebDAV
        self.namespaces = {
            'd': 'DAV:',
            'oc': 'http://owncloud.org/ns',
            'nc': 'http://nextcloud.org/ns'
        }
        
        # Autenticação
        self.auth = HTTPBasicAuth(self.username, self.password) if self.username and self.password else None
        
        # Configuração SSL
        self.verify_ssl = settings.NEXTCLOUD_VERIFY_SSL
        if not self.verify_ssl:
            logger.warning("⚠️  Verificação SSL desabilitada para NextCloud. Use apenas em desenvolvimento!")
            # Desabilita avisos de SSL não verificado
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _build_url(self, path: str) -> str:
        """
        Constrói a URL completa para um path no NextCloud.
        
        Args:
            path: Path relativo dentro da pasta do usuário (ex: 'pasta/subpasta')
        
        Returns:
            URL completa para o recurso
        
        Estrutura da URL:
        - webdav_base_url = base_url + webdav_path
        - URL final = webdav_base_url + user_path + path
        - Exemplo: https://example.com/remote.php/dav/files/username/pasta/arquivo.jpg
        """
        # Remove barras iniciais do path
        path = path.lstrip('/')
        
        # Constrói o path completo: user_path + path
        if path:
            full_path = f"{self.user_path}/{path}"
        else:
            full_path = self.user_path
        
        # URL final: webdav_base_url + full_path
        final_url = f"{self.webdav_base_url}{full_path}"
        
        logger.debug(f"Construindo URL - Base: {self.webdav_base_url}, Path: {full_path}, Final: {final_url}")
        
        return final_url
    
    def _parse_propfind_response(self, xml_content: str) -> List[Dict]:
        """
        Parseia a resposta XML de um PROPFIND e retorna lista de itens.
        
        Args:
            xml_content: Conteúdo XML da resposta
        
        Returns:
            Lista de dicionários com informações dos arquivos/pastas
        """
        items = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Encontra todos os elementos 'response' (cada arquivo/pasta)
            for response in root.findall('.//d:response', self.namespaces):
                href_elem = response.find('d:href', self.namespaces)
                if href_elem is None:
                    continue
                
                href = href_elem.text or ''
                
                # Pula o próprio diretório (href termina com /)
                if href.endswith('/') and href.count('/') == (self.user_path.count('/') + 1):
                    continue
                
                # Extrai propriedades
                propstat = response.find('d:propstat', self.namespaces)
                if propstat is None:
                    continue
                
                prop = propstat.find('d:prop', self.namespaces)
                if prop is None:
                    continue
                
                # Extrai informações
                item = {
                    'href': href,
                    'path': self._extract_relative_path(href),
                    'name': self._get_property(prop, 'd:displayname') or self._extract_filename(href),
                    'content_type': self._get_property(prop, 'd:getcontenttype') or '',
                    'content_length': self._parse_int(self._get_property(prop, 'd:getcontentlength')),
                    'last_modified': self._parse_datetime(self._get_property(prop, 'd:getlastmodified')),
                    'is_collection': self._is_collection(prop),
                    'file_id': self._get_property(prop, 'oc:fileid') or '',
                    'etag': self._get_property(prop, 'd:getetag') or ''
                }
                
                items.append(item)
        
        except ET.ParseError as e:
            logger.error(f"Erro ao parsear XML do NextCloud: {e}")
            raise ValueError(f"Resposta inválida do NextCloud: {e}")
        
        return items
    
    def _get_property(self, prop_elem: ET.Element, tag: str) -> Optional[str]:
        """Extrai o texto de uma propriedade XML."""
        elem = prop_elem.find(tag, self.namespaces)
        return elem.text if elem is not None and elem.text else None
    
    def _is_collection(self, prop_elem: ET.Element) -> bool:
        """Verifica se o item é uma coleção (pasta)."""
        resourcetype = prop_elem.find('d:resourcetype', self.namespaces)
        if resourcetype is None:
            return False
        return resourcetype.find('d:collection', self.namespaces) is not None
    
    def _extract_relative_path(self, href: str) -> str:
        """Extrai o path relativo a partir do href completo."""
        # Remove o prefixo do user_path
        if self.user_path in href:
            path = href.split(self.user_path, 1)[1]
            return path.lstrip('/')
        return href.lstrip('/')
    
    def _extract_filename(self, href: str) -> str:
        """Extrai o nome do arquivo do href."""
        return href.rstrip('/').split('/')[-1]
    
    def _parse_int(self, value: Optional[str]) -> int:
        """Converte string para int, retorna 0 se inválido."""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0
    
    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Converte string de data do WebDAV para datetime."""
        if not value:
            return None
        
        try:
            # Formato WebDAV: "Wed, 20 Jul 2022 05:12:23 GMT"
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(value)
        except (ValueError, TypeError):
            logger.warning(f"Erro ao parsear data: {value}")
            return None
    
    def list_folder(self, folder_path: str = '', depth: int = 1) -> List[Dict]:
        """
        Lista o conteúdo de uma pasta no NextCloud.
        
        Args:
            folder_path: Path relativo da pasta (vazio = raiz do usuário)
            depth: Profundidade da busca (0 = só a pasta, 1 = pasta + conteúdo)
        
        Returns:
            Lista de dicionários com informações dos arquivos/pastas
        
        Raises:
            requests.RequestException: Se houver erro na requisição
            ValueError: Se a resposta for inválida
        """
        url = self._build_url(folder_path)
        
        # XML para solicitar propriedades
        propfind_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
    <d:prop>
        <d:displayname/>
        <d:getcontenttype/>
        <d:getcontentlength/>
        <d:getlastmodified/>
        <d:resourcetype/>
        <d:getetag/>
        <oc:fileid/>
    </d:prop>
</d:propfind>"""
        
        headers = {
            'Content-Type': 'application/xml; charset=utf-8',
            'Depth': str(depth)
        }
        
        try:
            response = requests.request(
                'PROPFIND',
                url,
                data=propfind_xml,
                headers=headers,
                auth=self.auth,
                timeout=30,
                verify=self.verify_ssl
            )
            
            response.raise_for_status()
            
            return self._parse_propfind_response(response.text)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao listar pasta no NextCloud: {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 401:
                    raise ValueError("Credenciais inválidas do NextCloud")
                elif e.response.status_code == 404:
                    raise ValueError(f"Pasta não encontrada: {folder_path}")
                elif e.response.status_code == 403:
                    raise ValueError("Sem permissão para acessar esta pasta")
            raise
    
    def filter_images(self, items: List[Dict]) -> List[Dict]:
        """
        Filtra apenas imagens da lista de itens.
        
        Args:
            items: Lista de itens retornados por list_folder
        
        Returns:
            Lista filtrada contendo apenas imagens
        """
        image_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
                      'image/bmp', 'image/tiff', 'image/webp']
        
        images = []
        for item in items:
            # Ignora pastas
            if item.get('is_collection', False):
                continue
            
            # Verifica se é imagem pelo content_type
            content_type = item.get('content_type', '').lower()
            if any(img_type in content_type for img_type in image_types):
                images.append(item)
        
        return images
    
    def get_file(self, file_path: str) -> requests.Response:
        """
        Faz download de um arquivo do NextCloud.
        
        Args:
            file_path: Path relativo do arquivo
        
        Returns:
            Response do requests com stream do arquivo
        
        Raises:
            requests.RequestException: Se houver erro na requisição
        """
        url = self._build_url(file_path)
        
        try:
            response = requests.get(
                url,
                auth=self.auth,
                stream=True,
                timeout=60,
                verify=self.verify_ssl
            )
            
            response.raise_for_status()
            return response
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao baixar arquivo do NextCloud: {e}")
            if hasattr(e, 'response') and e.response:
                if e.response.status_code == 404:
                    raise ValueError(f"Arquivo não encontrado: {file_path}")
                elif e.response.status_code == 401:
                    raise ValueError("Credenciais inválidas do NextCloud")
                elif e.response.status_code == 403:
                    raise ValueError("Sem permissão para acessar este arquivo")
            raise


# Instância global do cliente (singleton)
_nextcloud_client: Optional[NextCloudClient] = None


def get_nextcloud_client() -> NextCloudClient:
    """
    Retorna a instância do cliente NextCloud (singleton).
    
    Returns:
        Instância do NextCloudClient
    """
    global _nextcloud_client
    
    if _nextcloud_client is None:
        _nextcloud_client = NextCloudClient()
    
    return _nextcloud_client

