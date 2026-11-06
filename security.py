"""Sessão sem estado: o cookie do Cajuí vai criptografado (Fernet) dentro do
cookie do navegador. O servidor não guarda nada, então reiniciar/dormir não
derruba o login. A senha do usuário nunca é armazenada."""
import json
import os
import time
from collections import defaultdict, deque

from cryptography.fernet import Fernet, InvalidToken

_key = os.getenv("FERNET_KEY")
if not _key:
    # Só para desenvolvimento local: a chave muda a cada start (sessões não sobrevivem).
    _key = Fernet.generate_key().decode()
    print("[AVISO] FERNET_KEY não definida; usando chave temporária.")
_fernet = Fernet(_key.encode())

SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "28800"))  # 8h


def pack(cookies: dict) -> str:
    return _fernet.encrypt(json.dumps(cookies).encode()).decode()


def unpack(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return json.loads(_fernet.decrypt(token.encode(), ttl=SESSION_MAX_AGE))
    except (InvalidToken, ValueError):
        return None


# Rate limit simples em memória (tentativas de login por IP).
_tentativas: dict[str, deque] = defaultdict(deque)


def login_bloqueado(ip: str, max_tentativas: int = 5, janela: int = 300) -> bool:
    agora = time.time()
    fila = _tentativas[ip]
    while fila and agora - fila[0] > janela:
        fila.popleft()
    return len(fila) >= max_tentativas


def registrar_tentativa(ip: str) -> None:
    _tentativas[ip].append(time.time())
