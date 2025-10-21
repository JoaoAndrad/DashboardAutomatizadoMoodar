# Como descriptografar as credenciais enviadas (guia para desenvolvedores)

Este documento explica passo a passo como um cliente pode descriptografar as credenciais que a API envia após o fluxo de ativação, usando a senha mestre informada pelo usuário.

Pré-requisitos

- Python 3.8+
- Biblioteca `cryptography` instalada:
  ```powershell
  pip install cryptography
  ```

Contexto técnico

- O servidor re-encripta cada arquivo original e retorna um `token` (texto Fernet) e um `salt` (base64) para cada arquivo.
- Para obter a chave Fernet correta o cliente deve:
  1. Base64-decodificar o salt recebido
  2. Derivar uma chave com PBKDF2-HMAC-SHA256 usando o salt, 600000 iterações e comprimento 32 bytes
  3. Converter a chave derivada para a forma URL-safe base64 com `base64.urlsafe_b64encode`
  4. Instanciar `cryptography.fernet.Fernet(derived_key)` e chamar `decrypt(token)`

Parâmetros (contrato)

- KDF: PBKDF2-HMAC-SHA256
- Iterações: 600000
- Length: 32
- Fernet key: base64.urlsafe_b64encode(kdf.derive(password))

Exemplo completo em Python

```python
import base64
import json
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet


def derive_fernet_key(password: str, salt_b64: str, iterations: int = 600000) -> bytes:
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations, backend=default_backend())
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def decrypt_token(token_text: str, fernet_key: bytes) -> bytes:
    f = Fernet(fernet_key)
    return f.decrypt(token_text.encode('utf-8'))


# exemplo de envelope recebido do servidor (já parseado em Python)
envelope = {
    'version': '1',
    'generated_at': '2025-10-17T12:34:56.789Z',
    'credentials': [
        { 'name': 'google_credentials.json.enc', 'token': 'gAAAAA...', 'salt': 'BASE64_SALT' },
        # ...
    ]
}

master_password = 'senhaDoUsuario'

for c in envelope.get('credentials', []):
    name = c['name']
    token = c['token']
    salt_b64 = c.get('salt')
    if not salt_b64:
        print('Sem salt para', name)
        continue
    try:
        fkey = derive_fernet_key(master_password, salt_b64)
        plaintext = decrypt_token(token, fkey)
        print('Descriptografado', name, '->', len(plaintext), 'bytes')
        # se for JSON, parse:
        try:
            import json
            parsed = json.loads(plaintext.decode('utf-8'))
            print('Conteúdo JSON:', parsed)
        except Exception:
            # nem todo ficheiro será JSON, pode ser binário
            print('Conteúdo bruto:', plaintext[:200])
    except Exception as e:
        print('Falha ao descriptografar', name, repr(e))
```

Boas práticas

- Não exponha a senha mestre em logs.
- Valide o tamanho do salt (deve ser 32 bytes após o base64-decode).
- Trate exceções separadamente para distinguir `InvalidToken` (senha/esquema incorreto) de outros erros (dados corrompidos).
- Faça backup das credenciais anteriores antes de sobrescrever.

Tratamento de erros comuns

- InvalidToken: senha incorreta ou token corrompido — informar o usuário para conferir a senha.
- base64.binascii.Error: salt malformado — pode indicar problema do lado do servidor; incluir o payload para suporte.
- Timeout/HTTP errors: repetir com backoff ou notificar operador.

