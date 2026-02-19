from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, JSON, CHAR, event, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid
import logging

logger = logging.getLogger(__name__)

class TipoUsuario(Base):
    __tablename__ = 'tipo_usuarios'
    id_tipo = Column(Integer, primary_key=True)
    nome = Column(String(50), nullable=False, unique=True)
    usuarios = relationship('Usuario', back_populates='tipo')

class Usuario(Base):
    __tablename__ = 'usuarios'
    id_usu = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_completo = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    telefone = Column(String(20), nullable=True)
    senha_hash = Column(CHAR(60), nullable=False)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    data_ultimo_login = Column(DateTime(timezone=True))
    ativo = Column(Boolean, nullable=False, default=True)
    id_tipo = Column(Integer, ForeignKey('tipo_usuarios.id_tipo'))
    tipo = relationship('TipoUsuario', back_populates='usuarios')
    administrador = relationship('UsuarioAdministrador', uselist=False, back_populates='usuario')
    convencional = relationship('UsuarioConvencional', uselist=False, back_populates='usuario')
    logs = relationship('LogAuditoria', back_populates='usuario')

class UsuarioAdministrador(Base):
    __tablename__ = 'usuarios_administradores'
    id_adm = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpf = Column(CHAR(11), nullable=False, unique=True, index=True)
    id_usu = Column(UUID(as_uuid=True), ForeignKey('usuarios.id_usu', ondelete='CASCADE'), nullable=False, unique=True)
    usuario = relationship('Usuario', back_populates='administrador')
    ambientes = relationship('Ambiente', back_populates='administrador')
    cadastros_permitidos = relationship('CadastroPermitido', back_populates='administrador')
    # Relacionamento com ConjuntoImagens removido - conjuntos são criados automaticamente via sincronização NextCloud

class CadastroPermitido(Base):
    __tablename__ = 'cadastros_permitidos'
    id_cad = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    usado = Column(Boolean, nullable=False, default=False)
    data_expiracao = Column(DateTime(timezone=True))
    id_tipo = Column(Integer, ForeignKey('tipo_usuarios.id_tipo'))
    id_adm = Column(UUID(as_uuid=True), ForeignKey('usuarios_administradores.id_adm', ondelete='CASCADE'), nullable=False)
    administrador = relationship('UsuarioAdministrador', back_populates='cadastros_permitidos')
    ativo = Column(Boolean, nullable=False, default=True)  # Exclusão lógica

class UsuarioConvencional(Base):
    __tablename__ = 'usuarios_convencionais'
    id_con = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpf = Column(CHAR(11), nullable=False, unique=True, index=True)
    id_usu = Column(UUID(as_uuid=True), ForeignKey('usuarios.id_usu', ondelete='CASCADE'), nullable=False, unique=True)
    usuario = relationship('Usuario', back_populates='convencional')
    ambientes = relationship('UsuarioAmbiente', back_populates='usuario_convencional')
    classificacoes = relationship('Classificacao', back_populates='usuario_convencional')
    progresso_ambientes = relationship('UsuarioAmbienteProgresso', back_populates='usuario_convencional')

class Ambiente(Base):
    __tablename__ = 'ambientes'
    id_amb = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo_amb = Column(String(255), nullable=False, unique=True)
    titulo_questionario = Column(String(255), nullable=True)  # Título do questionário do ambiente
    descricao_questionario = Column(Text, nullable=False)  # Descrição do questionário (obrigatório)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    id_adm = Column(UUID(as_uuid=True), ForeignKey('usuarios_administradores.id_adm', ondelete='CASCADE'), nullable=False)
    administrador = relationship('UsuarioAdministrador', back_populates='ambientes')
    usuarios = relationship('UsuarioAmbiente', back_populates='ambiente')
    conjuntos_imagens = relationship('AmbienteConjuntoImagens', back_populates='ambiente')
    opcoes = relationship('Opcao', back_populates='ambiente', cascade='all, delete-orphan')
    progresso_usuarios = relationship('UsuarioAmbienteProgresso', back_populates='ambiente')
    ativo = Column(Boolean, nullable=False, default=True)  # Exclusão lógica por parte do administrador
    utilizavel = Column(Boolean, nullable=False, default=True)  # Indica se o ambiente está utilizável (todas as pastas existem no NextCloud)

class UsuarioAmbiente(Base):
    __tablename__ = 'usuarios_ambientes'
    id_con = Column(UUID(as_uuid=True), ForeignKey('usuarios_convencionais.id_con', ondelete='CASCADE'), primary_key=True)
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), primary_key=True)
    data_associado = Column(DateTime(timezone=True), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)  # Exclusão lógica (cascata quando ambiente é excluído)
    usuario_convencional = relationship('UsuarioConvencional', back_populates='ambientes')
    ambiente = relationship('Ambiente', back_populates='usuarios')

class UsuarioAmbienteProgresso(Base):
    """
    Rastreia o progresso de classificação de um usuário em um ambiente.
    Usado para retomar de onde o usuário parou.
    """
    __tablename__ = 'usuarios_ambientes_progresso'
    id_con = Column(UUID(as_uuid=True), ForeignKey('usuarios_convencionais.id_con', ondelete='CASCADE'), primary_key=True)
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), primary_key=True)
    ultimo_data_proc_processado = Column(DateTime(timezone=True), nullable=True)  # data_proc da última imagem processada
    ultimo_content_hash_processado = Column(String(64), ForeignKey('imagens.content_hash', ondelete='SET NULL'), nullable=True)  # Hash da última imagem processada
    total_classificadas = Column(Integer, nullable=False, default=0)  # Total de imagens classificadas
    data_ultima_atividade = Column(DateTime(timezone=True), nullable=False)  # Timestamp da última classificação
    usuario_convencional = relationship('UsuarioConvencional', back_populates='progresso_ambientes')
    ambiente = relationship('Ambiente', back_populates='progresso_usuarios')

class Opcao(Base):
    """
    Representa uma opção de classificação para um ambiente.
    
    IMPORTANTE: O campo 'texto' é IMUTÁVEL após a criação.
    Alterar o texto de uma opção comprometeria a integridade do histórico
    de anotações/classificações, pois as classificações existentes referenciam
    este texto através do ID da opção.
    
    Para modificar uma opção, deve-se criar uma nova opção e, se necessário,
    migrar as classificações existentes.
    """
    __tablename__ = 'opcoes'
    id_opc = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    texto = Column(String(255), nullable=False)  # IMUTÁVEL após criação - não pode ser alterado
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), nullable=False)
    ambiente = relationship('Ambiente', back_populates='opcoes')
    classificacoes = relationship('Classificacao', back_populates='opcao')
    
    def __setattr__(self, key, value):
        """
        Impede a alteração do campo 'texto' após a criação do objeto.
        Isso garante a integridade do histórico de classificações.
        """
        if key == 'texto' and hasattr(self, 'texto') and self.texto is not None:
            # Se o objeto já existe no banco (tem ID) e já tem texto definido
            if hasattr(self, 'id_opc') and self.id_opc is not None:
                raise ValueError(
                    "O campo 'texto' de uma Opção é IMUTÁVEL após a criação. "
                    "Alterar este campo comprometeria a integridade do histórico de anotações. "
                    "Para modificar uma opção, crie uma nova opção."
                )
        super().__setattr__(key, value)


# Event listener para impedir atualização do campo 'texto' via SQLAlchemy
@event.listens_for(Opcao, 'before_update', propagate=True)
def prevent_texto_update(mapper, connection, target):
    """
    Event listener que impede a atualização do campo 'texto' de uma Opção.
    
    Este listener é acionado antes de qualquer operação UPDATE no banco de dados,
    garantindo que mesmo tentativas diretas de atualização sejam bloqueadas.
    """
    # Verificar se o objeto está sendo atualizado (não é uma inserção)
    if target.id_opc is not None:
        # Obter o estado original do objeto antes da atualização
        from sqlalchemy.orm import object_session
        session = object_session(target)
        if session:
            # Comparar o valor atual com o valor original
            state = session.inspect(target)
            if state.has_identity:
                history = state.get_history('texto', True)
                if history.has_changes():
                    logger.warning(
                        f"Tentativa de atualizar o campo 'texto' da Opção {target.id_opc} bloqueada. "
                        "O campo 'texto' é imutável para preservar a integridade do histórico de classificações."
                    )
                    raise ValueError(
                        "O campo 'texto' de uma Opção é IMUTÁVEL após a criação. "
                        "Alterar este campo comprometeria a integridade do histórico de anotações. "
                        "Para modificar uma opção, crie uma nova opção."
                    )


class AmbienteConjuntoImagens(Base):
    """
    Tabela auxiliar para relação N:N entre Ambiente e ConjuntoImagens.
    Permite que um ambiente tenha múltiplos conjuntos e um conjunto possa estar em múltiplos ambientes.
    """
    __tablename__ = 'ambientes_conjuntos_imagens'
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), primary_key=True)
    id_cnj = Column(UUID(as_uuid=True), ForeignKey('conjuntos_imagens.id_cnj', ondelete='CASCADE'), primary_key=True)
    data_associado = Column(DateTime(timezone=True), nullable=False)  # Timestamp da criação da associação
    ativo = Column(Boolean, nullable=False, default=True)  # Exclusão lógica (cascata quando ambiente é excluído)
    ambiente = relationship('Ambiente', back_populates='conjuntos_imagens')
    conjunto = relationship('ConjuntoImagens', back_populates='ambientes')

class ConjuntoImagens(Base):
    """
    Representa uma pasta do NextCloud.
    Cada pasta do NextCloud é automaticamente sincronizada e criada como um ConjuntoImagens.
    A associação com Ambiente é feita manualmente pelo administrador através da tabela AmbienteConjuntoImagens.
    """
    __tablename__ = 'conjuntos_imagens'
    id_cnj = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_conj = Column(String(255), nullable=False)  # Nome da pasta no NextCloud (pode mudar se pasta for renomeada)
    caminho_conj = Column(String(255), nullable=False)  # Caminho completo da pasta no NextCloud (pode mudar se pasta for movida)
    file_id = Column(String(255), nullable=False, unique=True)  # ID único da pasta no NextCloud (persistente)
    imagens_sincronizadas = Column(Boolean, nullable=False, default=False)  # Indica se todas as imagens da pasta foram sincronizadas (mecanismo de segurança para quedas de servidor)
    existe_no_nextcloud = Column(Boolean, nullable=False, default=True)  # Indica se a pasta ainda existe no NextCloud (política de persistência de dados)
    data_proc = Column(DateTime(timezone=True), nullable=False)  # Timestamp da primeira vez que a pasta foi processada/sincronizada
    data_sinc = Column(DateTime(timezone=True), nullable=False)  # Timestamp da última sincronização (atualizado quando há mudanças)
    ambientes = relationship('AmbienteConjuntoImagens', back_populates='conjunto')
    imagens = relationship('Imagem', back_populates='conjunto')

class Imagem(Base):
    """
    Representa uma imagem do NextCloud.
    A chave primária é o content_hash (SHA-256 do conteúdo binário da imagem),
    garantindo identificação única e persistente mesmo se nome/caminho mudarem.
    """
    __tablename__ = 'imagens'
    content_hash = Column(String(64), primary_key=True)  # SHA-256 do conteúdo binário (64 caracteres hexadecimais)
    nome_img = Column(String(255), nullable=False)  # Nome do arquivo no NextCloud (pode mudar se arquivo for renomeado)
    caminho_img = Column(String(255), nullable=False)  # Caminho completo do arquivo no NextCloud (pode mudar se arquivo for movido)
    metadados = Column(JSONB)  # Metadados do NextCloud: {file_id, etag, content_type, size, last_modified, width, height, ...}
    existe_no_nextcloud = Column(Boolean, nullable=False, default=True)  # Indica se a imagem ainda existe no NextCloud (política de persistência de dados)
    data_proc = Column(DateTime(timezone=True), nullable=False)  # Timestamp da primeira vez que a imagem foi processada e inserida no banco
    data_sinc = Column(DateTime(timezone=True), nullable=False)  # Timestamp da última sincronização (atualizado quando há mudanças em nome/caminho)
    id_cnj = Column(UUID(as_uuid=True), ForeignKey('conjuntos_imagens.id_cnj', ondelete='CASCADE'), nullable=False)
    conjunto = relationship('ConjuntoImagens', back_populates='imagens')
    classificacoes = relationship('Classificacao', back_populates='imagem')
    # Nota: content_hash é PK, então já possui índice único automaticamente

class Classificacao(Base):
    __tablename__ = 'classificacoes'
    __table_args__ = (
        # Índice composto para busca eficiente de classificações ativas por usuário e imagem
        Index('idx_classificacao_usuario_imagem_ativo', 'id_con', 'id_img', 'ativo'),
        # Índice composto para busca por usuário, imagem e opção (evita duplicatas)
        Index('idx_classificacao_usuario_imagem_opcao', 'id_con', 'id_img', 'id_opc'),
    )
    id_cla = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    data_modificado = Column(DateTime(timezone=True))
    id_con = Column(UUID(as_uuid=True), ForeignKey('usuarios_convencionais.id_con', ondelete='CASCADE'), nullable=False, index=True)
    id_img = Column(String(64), ForeignKey('imagens.content_hash', ondelete='CASCADE'), nullable=False, index=True)  # FK mudou de UUID para String (content_hash)
    id_opc = Column(UUID(as_uuid=True), ForeignKey('opcoes.id_opc', ondelete='RESTRICT'), nullable=False, index=True)
    ativo = Column(Boolean, nullable=False, default=True)  # Exclusão lógica - permite reclassificação sem perder histórico
    usuario_convencional = relationship('UsuarioConvencional', back_populates='classificacoes')
    imagem = relationship('Imagem', back_populates='classificacoes')
    opcao = relationship('Opcao', back_populates='classificacoes')

# NOVA TABELA DE EVENTOS DE AUDITORIA
class EventoAuditoria(Base):
    __tablename__ = 'eventos_auditoria'
    id_evento = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)
    logs = relationship('LogAuditoria', back_populates='evento')

class LogAuditoria(Base):
    __tablename__ = 'logs_auditoria'
    id_log = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usu = Column(UUID(as_uuid=True), ForeignKey('usuarios.id_usu'))
    evento_id = Column(Integer, ForeignKey('eventos_auditoria.id_evento'), nullable=False)
    data_evento = Column(DateTime(timezone=True), nullable=False, index=True)
    detalhes = Column(JSONB)
    usuario = relationship('Usuario', back_populates='logs')
    evento = relationship('EventoAuditoria', back_populates='logs')

class SyncStatus(Base):
    """
    Tabela para armazenar o estado da sincronização com NextCloud.
    Usada como cache para decisões de sincronização e rastreamento de status.
    Singleton: deve existir apenas um registro (id sempre = 1).
    """
    __tablename__ = 'sync_status'
    id = Column(Integer, primary_key=True, default=1)  # Sempre 1 (singleton)
    last_activity_api_sync = Column(DateTime(timezone=True))  # Timestamp da última sincronização via Activity API
    last_webdav_sync = Column(DateTime(timezone=True))  # Timestamp da última sincronização via WebDAV
    webdav_initial_sync_start = Column(DateTime(timezone=True))  # Timestamp de início da sincronização inicial WebDAV (para Activity API usar como referência)
    activity_api_available = Column(Boolean, nullable=False, default=True)  # Status da Activity API (disponível ou não)
    activity_api_last_check = Column(DateTime(timezone=True))  # Timestamp da última verificação da Activity API
    activity_api_failures = Column(Integer, nullable=False, default=0)  # Contador de falhas consecutivas da Activity API
    webdav_failures = Column(Integer, nullable=False, default=0)  # Contador de falhas consecutivas do WebDAV
    server_offline = Column(Boolean, nullable=False, default=False)  # Flag indicando se servidor NextCloud está completamente offline (ambos métodos falhando)
    last_health_check = Column(DateTime(timezone=True))  # Timestamp da última verificação de saúde do servidor
    sync_in_progress = Column(Boolean, nullable=False, default=False)  # Flag para evitar execuções simultâneas de sincronização
    last_sync_status = Column(String(50))  # Status da última sincronização: 'success', 'error', 'partial'
    last_sync_error = Column(Text)  # Mensagem de erro da última sincronização (se houver)
    last_sync_method = Column(String(50))  # Método usado na última sincronização: 'activity_api', 'webdav', 'initial'
    created_at = Column(DateTime(timezone=True), nullable=False)  # Timestamp de criação do registro
    updated_at = Column(DateTime(timezone=True), nullable=False)  # Timestamp da última atualização 