import re

descricoes = {
    'ADMIN_NOME_COMPLETO': 'Nome completo do admin inicial',
    'ADMIN_EMAIL': 'E-mail do admin inicial',
    'ADMIN_SENHA': 'Senha do admin inicial',
    'JWT_SECRET_KEY': 'Chave secreta para geração dos tokens JWT',
    'JWT_ALGORITHM': 'Algoritmo do JWT (ex: HS256)',
    'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': 'Tempo de expiração do token JWT (em minutos)',
    'DATABASE_URL': 'URL de conexão com o banco de dados',
    'POSTGRES_USER': 'Usuário do banco de dados PostgreSQL',
    'POSTGRES_PASSWORD': 'Senha do banco de dados PostgreSQL',
    'POSTGRES_DB': 'Nome do banco de dados PostgreSQL',
    'POSTGRES_HOST': 'Host do banco de dados PostgreSQL',
    'POSTGRES_PORT': 'Porta do banco de dados PostgreSQL',
    'API_HOST': 'Host da API',
    'API_PORT': 'Porta da API',
}

def gerar_env_example(env_path='.env', example_path='env.example'):
    linhas = []
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.rstrip('\n')
                if not linha or linha.strip().startswith('#'):
                    linhas.append(linha)
                    continue
                match = re.match(r'([^=]+)=(.*)', linha)
                if match:
                    chave = match.group(1).strip()
                    comentario = descricoes.get(chave, 'Preencha o valor adequado')
                    linhas.append(f'{chave}=  # {comentario}')
                else:
                    linhas.append(linha)
        with open(example_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(linhas) + '\n')
        print(f'Arquivo {example_path} gerado com sucesso!')
    except FileNotFoundError:
        print(f'Arquivo {env_path} não encontrado.')

if __name__ == '__main__':
    gerar_env_example() 