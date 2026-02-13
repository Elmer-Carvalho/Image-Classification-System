"""
Schemas para rotas de classificação de imagens.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ClassificacaoInfoOut(BaseModel):
    """Informações de uma classificação existente."""
    id_cla: str
    id_opc: str
    texto_opcao: str
    data_criado: datetime
    data_modificado: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImagemClassificacaoOut(BaseModel):
    """Informações de uma imagem com suas classificações (se existirem)."""
    content_hash: str
    nome_img: str
    caminho_img: str
    data_proc: datetime
    data_sinc: datetime
    download_url: str  # URL para baixar via proxy NextCloud
    classificacoes: List[ClassificacaoInfoOut] = []  # Lista de classificações (permite múltiplas opções)

    class Config:
        from_attributes = True


class ImagensClassificacaoResponse(BaseModel):
    """Resposta com lista de imagens para classificação."""
    imagens: List[ImagemClassificacaoOut]
    total: int
    tem_mais: bool  # Indica se há mais imagens disponíveis

    class Config:
        from_attributes = True


class AvancarRequest(BaseModel):
    """Request para avançar na lista de imagens."""
    content_hash: str = Field(..., description="Hash da imagem atual para buscar próximas")


class VoltarRequest(BaseModel):
    """Request para voltar na lista de imagens."""
    content_hash: str = Field(..., description="Hash da imagem atual para buscar anteriores")


class ClassificarRequest(BaseModel):
    """Request para classificar uma imagem com uma ou múltiplas opções."""
    content_hash: str = Field(..., description="Hash da imagem a ser classificada")
    id_opc: List[str] = Field(..., min_length=1, description="Lista de IDs das opções escolhidas (permite múltiplas opções)")

    class Config:
        json_schema_extra = {
            "example": {
                "content_hash": "abc123...",
                "id_opc": ["opcao-uuid-123", "opcao-uuid-456"]
            }
        }


class ClassificarResponse(BaseModel):
    """Resposta após classificar uma imagem."""
    message: str
    classificacoes: List[ClassificacaoInfoOut]  # Lista de classificações criadas/atualizadas
    total_classificadas: int

    class Config:
        from_attributes = True


class ClassificacoesImagemResponse(BaseModel):
    """Resposta com classificações de uma imagem específica para o usuário autenticado."""
    content_hash: str
    nome_img: str
    classificacoes: List[ClassificacaoInfoOut]  # Lista de classificações ativas do usuário

    class Config:
        from_attributes = True

