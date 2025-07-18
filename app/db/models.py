from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, JSON, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid

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
    id_usu = Column(UUID(as_uuid=True), ForeignKey('usuarios.id_usu', ondelete='CASCADE'), nullable=False, unique=True)
    usuario = relationship('Usuario', back_populates='administrador')
    ambientes = relationship('Ambiente', back_populates='administrador')
    cadastros_permitidos = relationship('CadastroPermitido', back_populates='administrador')
    conjuntos_imagens = relationship('ConjuntoImagens', back_populates='administrador')

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
    crm = Column(String(20))
    id_usu = Column(UUID(as_uuid=True), ForeignKey('usuarios.id_usu', ondelete='CASCADE'), nullable=False, unique=True)
    usuario = relationship('Usuario', back_populates='convencional')
    ambientes = relationship('UsuarioAmbiente', back_populates='usuario_convencional')
    classificacoes = relationship('Classificacao', back_populates='usuario_convencional')

class Ambiente(Base):
    __tablename__ = 'ambientes'
    id_amb = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo_amb = Column(String(255), nullable=False, unique=True)
    descricao = Column(Text)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    id_adm = Column(UUID(as_uuid=True), ForeignKey('usuarios_administradores.id_adm', ondelete='CASCADE'), nullable=False)
    administrador = relationship('UsuarioAdministrador', back_populates='ambientes')
    usuarios = relationship('UsuarioAmbiente', back_populates='ambiente')
    conjuntos_imagens = relationship('ConjuntoImagens', back_populates='ambiente')
    formularios = relationship('Formulario', back_populates='ambiente')
    ativo = Column(Boolean, nullable=False, default=True)  # Exclusão lógica

class UsuarioAmbiente(Base):
    __tablename__ = 'usuarios_ambientes'
    id_con = Column(UUID(as_uuid=True), ForeignKey('usuarios_convencionais.id_con', ondelete='CASCADE'), primary_key=True)
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), primary_key=True)
    data_associado = Column(DateTime(timezone=True), nullable=False)
    usuario_convencional = relationship('UsuarioConvencional', back_populates='ambientes')
    ambiente = relationship('Ambiente', back_populates='usuarios')

class Formulario(Base):
    __tablename__ = 'formularios'
    id_for = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text)
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), nullable=False)
    ambiente = relationship('Ambiente', back_populates='formularios')
    opcoes = relationship('Opcao', back_populates='formulario')

class Opcao(Base):
    __tablename__ = 'opcoes'
    id_opc = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    texto = Column(String(255), nullable=False)
    id_for = Column(UUID(as_uuid=True), ForeignKey('formularios.id_for', ondelete='CASCADE'), nullable=False)
    formulario = relationship('Formulario', back_populates='opcoes')
    classificacoes = relationship('Classificacao', back_populates='opcao')

class ConjuntoImagens(Base):
    __tablename__ = 'conjuntos_imagens'
    id_cnj = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_conj = Column(String(255), nullable=False)
    caminho_conj = Column(String(255), nullable=False)
    tipo_imagem = Column(String(50))
    descricao = Column(Text)
    processado = Column(Boolean, nullable=False, default=False)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    id_amb = Column(UUID(as_uuid=True), ForeignKey('ambientes.id_amb', ondelete='CASCADE'), nullable=False)
    id_adm = Column(UUID(as_uuid=True), ForeignKey('usuarios_administradores.id_adm', ondelete='CASCADE'), nullable=False)
    ambiente = relationship('Ambiente', back_populates='conjuntos_imagens')
    administrador = relationship('UsuarioAdministrador', back_populates='conjuntos_imagens')
    imagens = relationship('Imagem', back_populates='conjunto')

class Imagem(Base):
    __tablename__ = 'imagens'
    id_img = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_img = Column(String(255), nullable=False)
    caminho_img = Column(String(255), nullable=False)
    metadados = Column(JSONB)
    data_proc = Column(DateTime(timezone=True), nullable=False)
    id_cnj = Column(UUID(as_uuid=True), ForeignKey('conjuntos_imagens.id_cnj', ondelete='CASCADE'), nullable=False)
    conjunto = relationship('ConjuntoImagens', back_populates='imagens')
    classificacoes = relationship('Classificacao', back_populates='imagem')

class Classificacao(Base):
    __tablename__ = 'classificacoes'
    id_cla = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_criado = Column(DateTime(timezone=True), nullable=False)
    data_modificado = Column(DateTime(timezone=True))
    id_con = Column(UUID(as_uuid=True), ForeignKey('usuarios_convencionais.id_con', ondelete='CASCADE'), nullable=False, index=True)
    id_img = Column(UUID(as_uuid=True), ForeignKey('imagens.id_img', ondelete='CASCADE'), nullable=False, index=True)
    id_opc = Column(UUID(as_uuid=True), ForeignKey('opcoes.id_opc', ondelete='RESTRICT'), nullable=False, index=True)
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