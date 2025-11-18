#!/usr/bin/env python3
"""
Script para testar se a Activity API do NextCloud está disponível e acessível.
Útil para verificar se o app de Atividades está habilitado no servidor.
"""

import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.services.nextcloud_service import get_nextcloud_client

def test_activity_api():
    """Testa se a Activity API está disponível"""
    print("🔍 Verificando disponibilidade da Activity API do NextCloud...")
    print()
    
    try:
        client = get_nextcloud_client()
        
        print(f"📡 Servidor: {client.base_url}")
        print(f"👤 Usuário: {client.username}")
        print()
        
        print("⏳ Testando acesso à Activity API...")
        result = client.check_activity_api_available()
        
        print()
        print("=" * 60)
        print("📊 RESULTADO DA VERIFICAÇÃO")
        print("=" * 60)
        print()
        
        if result['available']:
            print("✅ Activity API está DISPONÍVEL e ACESSÍVEL")
            print()
            print("📝 Detalhes:")
            print(f"   • Endpoint: {result['endpoint']}")
            print(f"   • Status: {result['message']}")
            print()
            print("💡 Você pode usar a Activity API para:")
            print("   • Detectar mudanças específicas (arquivos adicionados/removidos)")
            print("   • Obter informações sobre quem fez as alterações")
            print("   • Sincronização mais eficiente")
            return True
        else:
            print("❌ Activity API NÃO está disponível ou acessível")
            print()
            print("📝 Detalhes:")
            print(f"   • Endpoint: {result['endpoint']}")
            print(f"   • Status: {result['message']}")
            if result.get('status_code'):
                print(f"   • Código HTTP: {result['status_code']}")
            print()
            print("💡 Possíveis causas:")
            if result.get('status_code') == 404:
                print("   • O app 'Atividades' não está instalado/ativado no servidor")
                print("   • Contate o administrador do NextCloud para habilitar")
            elif result.get('status_code') == 403:
                print("   • Você não tem permissão para acessar a Activity API")
                print("   • O app pode estar restrito apenas para administradores")
            elif result.get('status_code') == 401:
                print("   • Credenciais inválidas ou sem permissão")
            else:
                print("   • O app 'Atividades' pode não estar instalado/ativado")
                print("   • Problemas de conectividade ou configuração do servidor")
            print()
            print("💡 Alternativa recomendada:")
            print("   • Use a estratégia de ETag + file_id para sincronização")
            print("   • Funciona apenas com WebDAV (já disponível)")
            print("   • Não requer configuração adicional no servidor")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar Activity API: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_activity_api()
    print()
    print("=" * 60)
    sys.exit(0 if success else 1)

