"""
Schemas Pydantic para operações com NextCloud.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ImageItem(BaseModel):
    """Schema para informações de uma imagem do NextCloud."""
    name: str = Field(..., description="Nome do arquivo")
    path: str = Field(..., description="Path relativo do arquivo (use este path na rota de download)")
    content_type: str = Field(..., description="Tipo MIME da imagem")
    size: int = Field(..., description="Tamanho do arquivo em bytes", alias="content_length")
    last_modified: Optional[datetime] = Field(None, description="Data de última modificação")
    file_id: str = Field(..., description="ID único do arquivo no NextCloud")
    etag: str = Field(..., description="ETag do arquivo")
    download_url: str = Field(..., description="URL para download da imagem (path relativo para usar na rota GET /nextcloud/images/{file_path})")
    
    class Config:
        populate_by_name = True
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "imagem_renal_001.jpg",
                "path": "pasta/imagem_renal_001.jpg",
                "content_type": "image/jpeg",
                "size": 2456789,
                "last_modified": "2024-01-15T10:30:00Z",
                "file_id": "12345",
                "etag": "\"abc123def456\"",
                "download_url": "pasta/imagem_renal_001.jpg"
            }
        }


class ImageListResponse(BaseModel):
    """Schema para resposta paginada de lista de imagens."""
    images: List[ImageItem] = Field(..., description="Lista de imagens")
    page: int = Field(..., description="Página atual", ge=1)
    page_size: int = Field(..., description="Tamanho da página")
    total: int = Field(..., description="Total de imagens encontradas")
    total_pages: int = Field(..., description="Total de páginas")
    has_next: bool = Field(..., description="Indica se há próxima página")
    has_previous: bool = Field(..., description="Indica se há página anterior")
    
    class Config:
        json_schema_extra = {
            "example": {
                "images": [
                    {
                        "name": "imagem_renal_001.jpg",
                        "path": "pasta/imagem_renal_001.jpg",
                        "content_type": "image/jpeg",
                        "size": 2456789,
                        "last_modified": "2024-01-15T10:30:00Z",
                        "file_id": "12345",
                        "etag": "\"abc123def456\"",
                        "download_url": "pasta/imagem_renal_001.jpg"
                    }
                ],
                "page": 1,
                "page_size": 50,
                "total": 150,
                "total_pages": 3,
                "has_next": True,
                "has_previous": False
            }
        }

