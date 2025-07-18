#!/usr/bin/env python3
"""
Script de demonstração do sistema de monitoramento de imagens.
Mostra o funcionamento em tempo real com logs detalhados.
"""

import sys
import os
import time
import requests
import json
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings

def print_status(status_data):
    """Imprime status formatado"""
    print("📊 Status do Monitoramento:")
    print(f"   🟢 Ativo: {status_data.get('is_running', False)}")
    print(f"   🧵 Thread: {status_data.get('thread_alive', False)}")
    print(f"   ⏱️  Intervalo: {status_data.get('check_interval', 0)}s")
    print(f"   📁 Arquivos processados: {status_data.get('processed_files_count', 0)}")
    print(f"   📂 Pasta monitorada: {status_data.get('monitored_path', 'N/A')}")

def demo_monitoring():
    """Demonstração do sistema de monitoramento"""
    print("🎬 DEMONSTRAÇÃO DO SISTEMA DE MONITORAMENTO")
    print("=" * 50)
    print()
    
    # Verificar se a API está rodando
    print("🔍 Verificando sistema...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ Sistema não está rodando. Execute 'docker-compose up -d' primeiro.")
            return
    except:
        print("❌ Não foi possível conectar ao sistema.")
        return
    
    print("✅ Sistema está rodando!")
    print()
    
    # Mostrar status inicial
    print("📋 Status inicial:")
    status_response = requests.get("http://localhost:8000/monitor/status")
    if status_response.status_code == 200:
        initial_status = status_response.json()
        print_status(initial_status)
    print()
    
    # Criar pasta raw se não existir
    raw_path = Path(settings.RAW_IMAGES_PATH)
    raw_path.mkdir(parents=True, exist_ok=True)
    
    print("🎯 Iniciando demonstração...")
    print("   O sistema verifica novas imagens a cada 3 segundos")
    print("   Vamos adicionar alguns arquivos de teste")
    print()
    
    # Lista de arquivos para testar
    test_files = [
        ("arquivo.txt", "texto", False),  # Não deve ser processado
        ("imagem1.jpg", "conteudo da imagem", True),  # Deve ser processado
        ("imagem2.png", "outra imagem", True),  # Deve ser processado
    ]
    
    for filename, content, should_process in test_files:
        print(f"📁 Adicionando: {filename}")
        
        # Criar arquivo
        test_file = raw_path / filename
        with open(test_file, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Arquivo criado: {test_file}")
        
        # Aguardar e verificar processamento
        print("   ⏳ Aguardando processamento...")
        time.sleep(4)  # Aguardar um pouco mais que o intervalo de polling
        
        # Verificar status
        status_response = requests.get("http://localhost:8000/monitor/status")
        if status_response.status_code == 200:
            current_status = status_response.json()
            processed_count = current_status.get('processed_files_count', 0)
            
            if should_process:
                print(f"   📊 Arquivos processados: {processed_count}")
            else:
                print(f"   ⏭️  Arquivo ignorado (não é imagem)")
        
        print()
    
    # Mostrar imagens no banco
    print("📋 Verificando imagens no banco...")
    try:
        images_response = requests.get("http://localhost:8000/images/")
        if images_response.status_code == 200:
            images_data = images_response.json()
            total_images = images_data.get('total', 0)
            images_list = images_data.get('images', [])
            
            print(f"   📊 Total de imagens: {total_images}")
            
            if images_list:
                print("   📷 Imagens encontradas:")
                for img in images_list:
                    print(f"      - {img['filename']} ({img['status']})")
            else:
                print("   📭 Nenhuma imagem encontrada")
        else:
            print("   ❌ Erro ao buscar imagens")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    print()
    print("🎉 Demonstração concluída!")
    print()
    print("🔗 Links úteis:")
    print("   📖 API Docs: http://localhost:8000/docs")
    print("   📊 Status: http://localhost:8000/monitor/status")
    print("   🖼️  Imagens: http://localhost:8000/images/")
    print()
    print("📋 Para ver logs em tempo real:")
    print("   docker-compose logs -f app")

if __name__ == "__main__":
    demo_monitoring() 