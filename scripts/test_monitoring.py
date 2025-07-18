#!/usr/bin/env python3
"""
Script para testar o monitoramento de imagens com polling.
Este script simula a adição de imagens na pasta raw para testar o sistema.
"""

import sys
import os
import time
import requests
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings

def check_api_status():
    """Verifica se a API está rodando"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def get_monitor_status():
    """Obtém status do monitoramento"""
    try:
        response = requests.get("http://localhost:8000/monitor/status", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def create_test_image(filename: str, content: str = "Test image content"):
    """Cria um arquivo de teste na pasta raw"""
    raw_path = Path(settings.RAW_IMAGES_PATH)
    raw_path.mkdir(parents=True, exist_ok=True)
    
    test_file = raw_path / filename
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Arquivo de teste criado: {test_file}")
    return test_file

def test_monitoring():
    """Testa o monitoramento criando arquivos de teste"""
    print("=== Teste de Monitoramento com Polling ===")
    print(f"Pasta monitorada: {settings.RAW_IMAGES_PATH}")
    print()
    
    # Verificar se a API está rodando
    print("🔍 Verificando se a API está rodando...")
    if not check_api_status():
        print("❌ API não está rodando. Execute 'docker-compose up -d' primeiro.")
        return
    
    print("✅ API está rodando!")
    print()
    
    # Verificar status do monitor
    print("🔍 Verificando status do monitoramento...")
    status = get_monitor_status()
    if status:
        print(f"✅ Monitor ativo: {status}")
    else:
        print("❌ Monitor não está respondendo")
        return
    
    print()
    
    # Criar alguns arquivos de teste
    test_files = [
        "test1.txt",  # Deve ser ignorado (não é imagem)
        "test2.jpg",  # Deve ser processado
        "test3.png",  # Deve ser processado
    ]
    
    for filename in test_files:
        print(f"📁 Criando arquivo: {filename}")
        create_test_image(filename)
        
        # Aguardar processamento (mais tempo para polling)
        print(f"⏳ Aguardando processamento... (5 segundos)")
        time.sleep(5)
        
        # Verificar status novamente
        new_status = get_monitor_status()
        if new_status:
            print(f"📊 Status atual: {new_status['processed_files_count']} arquivos processados")
        
        print()
    
    print("🎉 Teste concluído!")
    print("📋 Verifique os logs da aplicação para ver se os arquivos foram detectados:")
    print("   docker-compose logs -f app")
    print()
    print("🌐 Acesse a API para ver as imagens:")
    print("   http://localhost:8000/images/")

if __name__ == "__main__":
    test_monitoring() 