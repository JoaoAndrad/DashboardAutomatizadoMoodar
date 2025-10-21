# Protocolo de Ativação — instruções para o cliente (implementação em Python)

Este documento descreve, em detalhe, o fluxo de ativação de uma máquina/cliente contra a API fornecida por este projeto, os payloads HTTP exatos esperados, o formato da resposta que contém credenciais re-encriptadas, e como verificar/desencriptar os tokens recebidos.

O objetivo é que você copie este arquivo para outro workspace onde será implementado o programa cliente em Python que fará o processo de ativação, receberá os arquivos encriptados e os armazenará corretamente.

## Visão geral do fluxo

1. (Opcional) Cliente cria uma solicitação de ativação: POST `/request_activation` — recebe `request_id`.
2. Administrador aprova a solicitação (via painel admin) e gera um código de ativação (8 dígitos).
3. Cliente confirma o código enviado pelo administrador: POST `/confirm_code` — verifica se o código é válido.
4. Cliente envia o `master_password` junto com o `code`: POST `/submit_master_key` — a API executa o utilitário `rewrap_credentials.py` no servidor e responde com um `envelope` que contém N credenciais re-encriptadas.
5. Cliente armazena localmente os tokens e salts, e então deriva a chave e tenta descriptografar para verificar integridade.

> Observação: existe também o endpoint `/activate` que retorna `device_id` e um `wrapped_dek` — esse fluxo é orientado a registro de dispositivo e geração de chave de dados (DEK). Para transferência de credenciais o endpoint de interesse é `/submit_master_key`.

---

## Endpoints relevantes (resumido)

- POST /request_activation

  - Payload (JSON): { device_info?: object, contact?: string|null, metadata?: object }
  - Response: { request_id: number, message: 'request created' }

- POST /confirm_code

  - Payload (JSON): { code: string }
  - Response (200): { ok: true, message: 'code valid' }
  - Errors: 400/403/404 com mensagens de erro detalhadas

- POST /submit_master_key
  - Payload (JSON): { code: string, master_password: string }
  - Response (200): JSON envelope com credenciais (ver abaixo)
  - Erros: 400 quando o `rewrap` relata problemas; 500 quando o utilitário falha inesperadamente

---

## Formato exato do envelope retornado por `/submit_master_key`

Quando a API executa `rewrap_credentials.py`, ela espera que o script imprima um JSON com o formato:

```
{
  "files": [
    { "name": "<nome_do_arquivo_enc>", "token": "<fernet-token-text>", "salt": "<salt_base64>", "meta": <opcional> },
    ...
  ]
}
```

O servidor empacota isso em um `envelope` HTTP que o cliente recebe como resposta JSON (exemplo):

```
{
  "version": "1",
  "generated_at": "2025-10-17T12:34:56.789Z",
  "credentials": [
    { "name": "google_credentials.json.enc", "token": "gAAAA...", "token_format": "fernet", "salt": "<base64>", "meta": null },
    ...
  ],
  "errors": [ ... ] // opcional
}
```

Campos importantes:

- `credentials`: array de objetos, cada um representando um ficheiro de credencial re-encriptado
- `name`: string — nome do ficheiro (geralmente termina em `.enc`, o servidor preserva o nome original)
- `token`: string — token Fernet (URL-safe base64 string) que representa o conteúdo encriptado
- `token_format`: deve ser `fernet` (atualmente)
- `salt`: string — salt usado para derivar a chave para esse ficheiro (base64 padrão)

O número de arquivos (N) é variável — depende de quantas credenciais o servidor tem em `.moodar_credentials`. No workspace atual de exemplo existem 5 arquivos `.enc`, então o servidor retorna 5 entradas.

---

## Como o token foi gerado (parâmetros de encriptação)

- Algoritmo de derivação: PBKDF2-HMAC-SHA256
- Comprimento da chave derivada: 32 bytes
- Iterações: 600000 (seabém do código do servidor/rewrap)
- Salt: 32 bytes gerados aleatoriamente no servidor; no envelope ele é recebido como base64
- Chave Fernet final: base64.urlsafe_b64encode(derived_key)
- Token: produzido por Fernet.encrypt(plaintext) e convertido para string UTF-8

Em termos práticos, para verificar/descriptografar um token recebido:

1. salt_b64 -> salt = base64.b64decode(salt_b64)
2. kdf = PBKDF2HMAC(SHA256, length=32, salt=salt, iterations=600000)
3. key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
4. f = Fernet(key)
5. plaintext = f.decrypt(token.encode('utf-8'))

---

## Convenção de nomes e arquivos que o cliente deve gravar localmente

Quando o cliente receber o envelope, recomenda-se armazenar os arquivos assim:

- diretório base do cliente para credenciais (ex.: `./credenciais/`)
- para cada item `c` em `envelope.credentials`:
  - gravar `c.token` (texto) em `credenciais/<c.name>` (ex.: `credenciais/google_credentials.json.enc`)
  - gravar `c.salt` (base64 string) em `credenciais/<c.name>.salt` (ex.: `credenciais/google_credentials.json.enc.salt`)
  - se `c.meta` existir, gravar `credenciais/<c.name>.meta.json`

Exemplo de layout local após salvar 3 arquivos:

```
credenciais/
  google_credentials.json.enc
  google_credentials.json.enc.salt
  companies_cache.json.enc
  companies_cache.json.enc.salt
  ...
```

Detalhe: `c.name` já contém a extensão `*.enc` e deve ser usada sem modificações para facilitar correlação com o servidor.

---

## Exemplo de implementação em Python (requests + cryptography)

- Requisitos: requests, cryptography

Exemplos mínimos (trechos) — o cliente final deve tratar erros, timeouts e retries.

1. Confirmar código:

```python
import requests

API = 'https://seu-servidor.example'

resp = requests.post(f'{API}/confirm_code', json={'code': '12345678'})
resp.raise_for_status()
print(resp.json())
```

2. Enviar master_password e receber envelope com credenciais:

```python
resp = requests.post(f'{API}/submit_master_key', json={'code': '12345678', 'master_password': 'senhaDoCliente'})
resp.raise_for_status()
envelope = resp.json()
```

3. Salvar arquivos e verificar descriptografia:

```python
import os, base64
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

OUT = Path('credenciais')
OUT.mkdir(exist_ok=True)

for c in envelope.get('credentials', []):
    name = c['name']
    token = c['token']
    salt_b64 = c.get('salt')
    (OUT / name).write_text(token, encoding='utf-8')
    if salt_b64:
        (OUT / (name + '.salt')).write_text(salt_b64, encoding='utf-8')

    # Verificação
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000, backend=default_backend())
    key = base64.urlsafe_b64encode(kdf.derive('senhaDoCliente'.encode()))
    f = Fernet(key)
    plaintext = f.decrypt(token.encode('utf-8'))
    print(name, '->', len(plaintext), 'bytes OK')
```

Nota: tratamento de exceções deve reportar falhas e salvar logs; se algum token falhar a descriptografia, o cliente deve notificar o usuário/operador e não sobrescrever as referências anteriores sem backup.

---

## Casos de erro e códigos HTTP

- 400: Requisição inválida (por exemplo `code` ausente ou `rewrap` relatou problemas)
- 403: Código existente, mas não aprovado ou autorizado
- 404: Código inválido
- 500: Erro interno (script `rewrap` falhou ou erro no servidor)

Quando a API retorna erro 400 por conta do `rewrap`, ela pode repassar o conteúdo JSON que o script produziu, por exemplo `{ "error": "master key not found" }` — o cliente deve ler e exibir essa mensagem.

---

## Observações operacionais e segurança

- Transmita todas as requisições por HTTPS.
- Nunca logue `master_password` em texto claro em logs persistentes.
- Trate o número de iterações (600000) como parte do contrato; se o servidor mudar, será necessária atualização no cliente apenas para compatibilidade de diagnóstico (mas em princípio o cliente não precisa saber as iterações a priori — apenas para verificar offline).
- Salve cópias de backup antes de sobrescrever credenciais locais.

---

## Quantos arquivos serão enviados? como serão nomeados?

- O servidor enviará uma entrada por cada arquivo `*.enc` que ele possui em `.moodar_credentials`.
- Nome: o campo `name` contém o nome completo do ficheiro tal como está no servidor (ex.: `google_credentials.json.enc`).
- Extensão: o token deve ser guardado como um ficheiro texto (UTF-8) com a extensão `.enc`.
- Salt: gravado em arquivo com sufixo `.salt` usando o mesmo nome do ficheiro (ex.: `google_credentials.json.enc.salt`) e seu conteúdo é a string base64 retornada pelo servidor.

No workspace de exemplo anexado, o servidor reenviará 5 arquivos (os 5 `.enc` presentes em `.moodar_credentials`):

- atualizarbases2025-5c774c833ddb.json.enc
- client_secret_883998...apps.googleusercontent.com.json.enc
- companies_cache.json.enc
- google_credentials.json.enc
- google_oauth_credentials.json.enc

---

## Checklist para a equipe que vai implementar o cliente

1. Usar `requests` com timeouts apropriados para todas as chamadas.
2. Implementar retry/backoff para chamadas de rede flakey (especialmente `submit_master_key`).
3. Persistir tokens e salts em `credenciais/` conforme convenção.
4. Verificar descriptografia imediatamente após salvar; em caso de falha, não substituir versões anteriores sem backup.
5. Expor logs amigáveis para suporte em caso de erro no `rewrap` (capturar mensagem de erro repassada pelo servidor).

---

Se quiser, eu posso gerar um script cliente inicial em Python (arquivo executável) que implemente todo esse fluxo (confirm_code + submit_master_key + salvar + verificar) como exemplo para o time — quer que eu gere isso também?
