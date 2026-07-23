"""
Serviço de configuração de LLM e credenciais.

Fonte da verdade: tabela `llm_config` (Postgres, JSONB). Cada credencial tem um
`storage_mode`:

- "cloud": o segredo é guardado CIFRADO no banco (Fernet / DAISE_SECRET_KEY).
- "local": o segredo NÃO vai para o banco; fica em arquivo no host
  (`data/config/llm_config_local.json`, gitignored) — para quem não quer subir
  a credencial para a nuvem.

A API nunca devolve segredos: expõe apenas `hasKey`/`maskedKey`/`storageMode`.
A resolução do segredo em texto puro acontece só no servidor, na hora de chamar
o provedor (Agent / GitHub).
"""
import json
import os

from app.src.db import session_scope
from app.src.db_models import LlmConfigRow
from app.src.security import crypto

_BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
LOCAL_SECRETS_PATH = os.path.join(
    _BACKEND_DIR, "data", "config", "llm_config_local.json"
)

# provedor -> nome do campo que guarda o segredo
SECRET_KEYS = {
    "gemini": "committedApiKey",
    "openai": "committedApiKey",
    "github": "committedToken",
}
VALID_MODES = ("cloud", "local")


def _default_config() -> dict:
    return {
        "__lastSavedConfig": {
            "provider": "gemini",
            "model": "",
            "temperature": 0,
            "tokens": "0",
        },
        "gemini": {"committedApiKey": "", "storage_mode": "cloud"},
        "openai": {"committedApiKey": "", "storage_mode": "cloud"},
        "ollama": {"committedEndpoint": ""},
        "github": {"committedToken": "", "storage_mode": "cloud"},
    }


# ─── persistência bruta ──────────────────────────────────────────────────────

def _load_db() -> dict:
    with session_scope() as s:
        row = s.get(LlmConfigRow, 1)
        if row is None or not row.data:
            return _default_config()
        # mescla sobre o default para tolerar chaves ausentes
        cfg = _default_config()
        _deep_merge(cfg, row.data)
        return cfg


def _save_db(cfg: dict) -> None:
    with session_scope() as s:
        row = s.get(LlmConfigRow, 1)
        if row is None:
            row = LlmConfigRow(id=1, data=cfg)
            s.add(row)
        else:
            row.data = cfg


def _load_local() -> dict:
    if not os.path.exists(LOCAL_SECRETS_PATH):
        return {}
    try:
        with open(LOCAL_SECRETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_local(local: dict) -> None:
    os.makedirs(os.path.dirname(LOCAL_SECRETS_PATH), exist_ok=True)
    with open(LOCAL_SECRETS_PATH, "w", encoding="utf-8") as f:
        json.dump(local, f, ensure_ascii=False, indent=2)


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ─── leitura/escrita de segredos ─────────────────────────────────────────────

def _read_secret(provider: str, field: str, provcfg: dict, local: dict) -> str:
    """Retorna o segredo em texto puro (decifra se cloud, lê arquivo se local)."""
    mode = (provcfg.get("storage_mode") or "cloud").lower()
    if mode == "local":
        return (local.get(provider, {}) or {}).get(field, "") or ""
    return crypto.decrypt(provcfg.get(field, "") or "")


def _has_stored_secret(provider: str, field: str, provcfg: dict, local: dict) -> bool:
    """Diz se há segredo guardado, SEM precisar decifrar (para exibição na API)."""
    mode = (provcfg.get("storage_mode") or "cloud").lower()
    if mode == "local":
        return bool((local.get(provider, {}) or {}).get(field))
    return bool(provcfg.get(field))


def _set_secret(provider, field, plaintext, mode, cfg, local) -> None:
    provcfg = cfg.setdefault(provider, {})
    provcfg["storage_mode"] = mode
    if mode == "local":
        provcfg[field] = ""  # nada no banco
        local.setdefault(provider, {})[field] = plaintext
    else:  # cloud
        provcfg[field] = crypto.encrypt(plaintext)
        if provider in local:
            local[provider].pop(field, None)


# ─── API pública ─────────────────────────────────────────────────────────────

def get_config_for_api() -> dict:
    """Config para o frontend, SEM segredos (apenas hasKey/maskedKey/storageMode)."""
    cfg = _load_db()
    local = _load_local()
    out = {"__lastSavedConfig": cfg.get("__lastSavedConfig", {})}

    for prov, field in SECRET_KEYS.items():
        provcfg = cfg.get(prov, {})
        has = _has_stored_secret(prov, field, provcfg, local)
        # Máscara é best-effort: se o segredo foi cifrado com outra chave-mestra,
        # não derruba a API — apenas sinaliza que está ilegível.
        masked = ""
        if has:
            try:
                masked = crypto.mask(_read_secret(prov, field, provcfg, local))
            except Exception:
                masked = "•••• (ilegível)"
        draft_field = "apiKey" if field == "committedApiKey" else "token"
        out[prov] = {
            draft_field: "",
            field: "",  # nunca vaza o segredo/ciphertext
            "hasKey": has,
            "maskedKey": masked,
            "storageMode": (provcfg.get("storage_mode") or "cloud").lower(),
        }

    # Ollama endpoint não é segredo: devolvido em texto puro.
    endpoint = cfg.get("ollama", {}).get("committedEndpoint", "")
    out["ollama"] = {"endpoint": endpoint, "committedEndpoint": endpoint}
    return out


def save_config(partial: dict) -> dict:
    """Mescla o payload parcial na config, respeitando storage_mode e cifragem."""
    if not isinstance(partial, dict):
        raise ValueError("Payload inválido.")

    cfg = _load_db()
    local = _load_local()

    if isinstance(partial.get("__lastSavedConfig"), dict):
        cfg.setdefault("__lastSavedConfig", {}).update(partial["__lastSavedConfig"])

    # Ollama endpoint (texto puro)
    if isinstance(partial.get("ollama"), dict):
        oll = partial["ollama"]
        endpoint = oll.get("committedEndpoint")
        if endpoint is None:
            endpoint = oll.get("endpoint")
        if endpoint is not None:
            cfg.setdefault("ollama", {})["committedEndpoint"] = str(endpoint).strip()

    for prov, field in SECRET_KEYS.items():
        if not isinstance(partial.get(prov), dict):
            continue
        pdata = partial[prov]
        provcfg = cfg.setdefault(prov, {"storage_mode": "cloud"})
        current_mode = (provcfg.get("storage_mode") or "cloud").lower()
        new_mode = (pdata.get("storageMode") or pdata.get("storage_mode") or current_mode).lower()
        if new_mode not in VALID_MODES:
            new_mode = "cloud"

        draft_field = "apiKey" if field == "committedApiKey" else "token"
        incoming = pdata.get(field)
        if incoming is None:
            incoming = pdata.get(draft_field)
        incoming = (incoming or "").strip()
        is_placeholder = incoming.startswith("••••")

        if incoming and not is_placeholder:
            # segredo novo informado pelo usuário
            _set_secret(prov, field, incoming, new_mode, cfg, local)
        elif new_mode != current_mode:
            # segredo inalterado, mas mudou o modo de armazenamento: migra
            existing = _read_secret(prov, field, provcfg, local)
            _set_secret(prov, field, existing, new_mode, cfg, local)
        else:
            provcfg["storage_mode"] = new_mode

    _save_db(cfg)
    _save_local(local)
    return get_config_for_api()


def resolve_secret(provider: str) -> str:
    """Segredo em texto puro para uso interno (Agent/GitHub). Nunca exposto na API."""
    provider = (provider or "").lower()
    if provider == "ollama":
        return _load_db().get("ollama", {}).get("committedEndpoint", "")
    field = SECRET_KEYS.get(provider)
    if not field:
        return ""
    cfg = _load_db()
    return _read_secret(provider, field, cfg.get(provider, {}), _load_local())
