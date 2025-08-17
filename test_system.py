#!/usr/bin/env python3
"""
Script de teste para verificar se o sistema está funcionando corretamente.
"""

import requests
import time

def test_system():
    """Testa as principais funcionalidades do sistema"""
    base_url = "http://localhost:5000"
    
    print("🧪 Testando sistema de bate-papo...")
    print("=" * 50)
    
    # Teste 1: Página principal
    print("1. Testando página principal...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("   ✅ Página principal funcionando")
        else:
            print(f"   ❌ Página principal retornou {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro ao acessar página principal: {e}")
    
    # Teste 2: Página de login
    print("2. Testando página de login...")
    try:
        response = requests.get(f"{base_url}/auth/login", timeout=5)
        if response.status_code == 200:
            print("   ✅ Página de login funcionando")
        else:
            print(f"   ❌ Página de login retornou {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro ao acessar página de login: {e}")
    
    # Teste 3: Página de registro
    print("3. Testando página de registro...")
    try:
        response = requests.get(f"{base_url}/auth/register", timeout=5)
        if response.status_code == 200:
            print("   ✅ Página de registro funcionando")
        else:
            print(f"   ❌ Página de registro retornou {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro ao acessar página de registro: {e}")
    
    # Teste 4: Tentativa de acesso a área protegida
    print("4. Testando acesso a área protegida...")
    try:
        response = requests.get(f"{base_url}/rooms/", timeout=5, allow_redirects=False)
        if response.status_code == 302:  # Redirecionamento para login
            print("   ✅ Proteção de rotas funcionando")
        else:
            print(f"   ❌ Proteção de rotas retornou {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro ao testar proteção de rotas: {e}")
    
    print("=" * 50)
    print("🎯 Testes concluídos!")
    print("\n📝 Para testar o sistema completo:")
    print("1. Acesse: http://localhost:5000")
    print("2. Clique em 'Cadastrar' para criar uma conta")
    print("3. Faça login com suas credenciais")
    print("4. Crie uma sala e teste as funcionalidades")

if __name__ == '__main__':
    test_system()




