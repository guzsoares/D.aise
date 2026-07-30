"""
Contexto do usuário atual.

Enquanto o login (registro/sessão) não está ligado na UI, a aplicação opera
como um usuário "bootstrap" — assim o app funciona ponta a ponta no novo schema
multiusuário. Quando a autenticação real for plugada, basta trocar
`current_user_id()` para resolver o usuário da requisição/sessão.
"""
import os

from app.src.db import session_scope
from app.src.db_models import User, UserSettings
from app.src.security import passwords

BOOTSTRAP_EMAIL = os.getenv("DAISE_BOOTSTRAP_EMAIL", "admin@daise.local")

_cached_id: str | None = None


def ensure_bootstrap_user() -> str:
    """Cria (se necessário) o usuário bootstrap + suas preferências e retorna o id."""
    global _cached_id
    with session_scope() as s:
        u = s.query(User).filter(User.email == BOOTSTRAP_EMAIL).one_or_none()
        if u is None:
            pw = os.getenv("DAISE_BOOTSTRAP_PASSWORD", "changeme")
            u = User(
                email=BOOTSTRAP_EMAIL,
                name="Admin",
                role="admin",
                password_hash=passwords.hash_password(pw),
            )
            u.settings = UserSettings()
            s.add(u)
            s.flush()
        elif u.settings is None:
            u.settings = UserSettings()
            s.flush()
        _cached_id = u.id
    return _cached_id


def current_user_id() -> str:
    """Id do usuário atual (hoje, o bootstrap). Ponto único a trocar quando houver login."""
    if _cached_id:
        return _cached_id
    return ensure_bootstrap_user()


def reset_cache() -> None:
    """Limpa o cache do id (usado em testes)."""
    global _cached_id
    _cached_id = None
