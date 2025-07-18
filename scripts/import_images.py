#!/usr/bin/env python3
"""
Script para importação manual de imagens da pasta raw para o banco de dados.
Este script pode ser executado independentemente da aplicação principal.
"""

import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.image_service import ImageProcessor

def import_images():
    """Importa todas as imagens da pasta raw"""
    print("Iniciando importação de imagens...")
    
    # Criar sessão do banco
    db = SessionLocal()
    
    try:
        # Criar processador
        processor = ImageProcessor(db)
        
        # Processar imagens existentes
        processor.process_existing_images()
        
        print("Importação concluída!")
        
    except Exception as e:
        print(f"Erro durante a importação: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import_images() 