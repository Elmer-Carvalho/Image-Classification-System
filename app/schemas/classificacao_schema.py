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
    """Informações de uma imagem com sua classificação (se existir)."""
    content_hash: str
    nome_img: str
    caminho_img: str
    data_proc: datetime
    data_sinc: datetime
    download_url: str  # URL para baixar via proxy NextCloud
    classificacao: Optional[ClassificacaoInfoOut] = None  # None se não foi classificada

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
    """Request para classificar uma imagem."""
    content_hash: str = Field(..., description="Hash da imagem a ser classificada")
    id_opc: str = Field(..., description="ID da opção escolhida")

    class Config:
        json_schema_extra = {
            "example": {
                "content_hash": "abc123...",
                "id_opc": "opcao-uuid-123"
            }
        }


class ClassificarResponse(BaseModel):
    """Resposta após classificar uma imagem."""
    message: str
    classificacao: ClassificacaoInfoOut
    total_classificadas: int

    class Config:
        from_attributes = True

