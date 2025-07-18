import bcrypt

# Gera um hash seguro para a senha

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Verifica se a senha corresponde ao hash

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validar_cpf(cpf: str) -> bool:
    """Valida CPF (apenas números, 11 dígitos, algoritmo de validação)."""
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i+1) - num) for num in range(0, i))
        digito = ((soma * 10) % 11) % 10
        if int(cpf[i]) != digito:
            return False
    return True

def validar_nome(nome: str) -> bool:
    """Valida nome completo (mínimo 2 palavras, cada uma com pelo menos 2 letras)."""
    partes = [p for p in nome.strip().split() if len(p) >= 2]
    return len(partes) >= 2

def validar_forca_senha(senha: str) -> bool:
    """Valida força mínima da senha (mínimo 8 caracteres, 1 maiúscula, 1 minúscula, 1 número)."""
    if len(senha) < 8:
        return False
    tem_maiuscula = any(c.isupper() for c in senha)
    tem_minuscula = any(c.islower() for c in senha)
    tem_numero = any(c.isdigit() for c in senha)
    return tem_maiuscula and tem_minuscula and tem_numero 