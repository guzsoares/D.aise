"""
Migra os dados dos arquivos JSON legados para o PostgreSQL.

Idempotente: pode rodar mais de uma vez (faz upsert). Executa:

  1. Cria as tabelas (se ainda não existirem).
  2. Seed dos prompts versionados      (prompts/prompts.json).
  3. Importa os prompts padrão          (data/config/default_prompts.json), com
     fallback automático para o 1º prompt ativo de cada tipo.
  4. Importa os projetos                 (data/repositories/*.json).
  5. Importa a config de LLM/credenciais (data/config/llm_config.json), cifrando
     os segredos no modo 'cloud' quando DAISE_SECRET_KEY está definida (senão
     salva no modo 'local', em arquivo, para não perder dado).

Uso (a partir de backend/):
    python -m scripts.migrate_json_to_pg
"""
import json
import os
import sys

# Garante que `import app...` funcione ao rodar como script.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_BACKEND_DIR, ".env"))


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  ! falha ao ler {path}: {e}")
        return None


def seed_prompts():
    from app.src.db import session_scope
    from app.src.db_models import PromptRow

    prompts = _read_json(os.path.join(_BACKEND_DIR, "prompts", "prompts.json")) or {}
    if not prompts:
        print("  (nenhum prompt em prompts/prompts.json)")
        return
    count = 0
    with session_scope() as s:
        for pid, p in prompts.items():
            row = s.get(PromptRow, pid)
            if row is None:
                row = PromptRow(id=pid)
                s.add(row)
            row.name = p.get("name") or ""
            row.type = p.get("type") or ""
            row.description = p.get("description", "")
            row.content = p.get("content") or ""
            row.is_active = p.get("is_active", True)
            count += 1
    print(f"  {count} prompt(s) importado(s).")


def seed_defaults():
    from app.src.db import session_scope
    from app.src.db_models import PromptRow, DefaultPromptRow

    defaults = _read_json(
        os.path.join(_BACKEND_DIR, "data", "config", "default_prompts.json")
    ) or {}

    with session_scope() as s:
        # 1) defaults explícitos do arquivo
        desired = {t: pid for t, pid in defaults.items() if pid}

        # 2) fallback: tipo sem default -> 1º prompt ativo daquele tipo
        types = {t for (t,) in s.query(PromptRow.type).distinct()}
        for ptype in types:
            if ptype in desired:
                continue
            first = (
                s.query(PromptRow)
                .filter(PromptRow.type == ptype, PromptRow.is_active.is_(True))
                .order_by(PromptRow.created_at)
                .first()
            )
            if first:
                desired[ptype] = first.id

        # 3) upsert único por tipo
        for ptype, pid in desired.items():
            row = s.get(DefaultPromptRow, ptype)
            if row is None:
                s.add(DefaultPromptRow(type=ptype, prompt_id=pid))
            else:
                row.prompt_id = pid
    print("  defaults por tipo garantidos.")


def import_projects():
    from app.src.model.project_model import Project

    repo_dir = os.path.join(_BACKEND_DIR, "data", "repositories")
    if not os.path.isdir(repo_dir):
        print("  (data/repositories/ não existe — nenhum projeto para importar)")
        return
    count = 0
    for filename in sorted(os.listdir(repo_dir)):
        if not filename.endswith(".json"):
            continue
        data = _read_json(os.path.join(repo_dir, filename))
        if not isinstance(data, dict):
            continue
        Project().save_json(dict(data))
        count += 1
    print(f"  {count} projeto(s) importado(s).")


def import_llm_config():
    from app.src.security import crypto
    from app.src.service import llm_config_service

    old = _read_json(
        os.path.join(_BACKEND_DIR, "data", "config", "llm_config.json")
    )
    if not old:
        print("  (sem llm_config.json legado)")
        return

    key_available = crypto.is_configured()
    mode = "cloud" if key_available else "local"
    if not key_available:
        print(
            "  ! DAISE_SECRET_KEY ausente: credenciais serão migradas no modo "
            "'local' (arquivo). Defina a chave e re-rode para cifrar na nuvem."
        )

    partial = {}
    if isinstance(old.get("__lastSavedConfig"), dict):
        partial["__lastSavedConfig"] = old["__lastSavedConfig"]

    for prov, field in (
        ("gemini", "committedApiKey"),
        ("openai", "committedApiKey"),
        ("github", "committedToken"),
    ):
        secret = (old.get(prov) or {}).get(field, "")
        if secret:
            partial[prov] = {field: secret, "storage_mode": mode}

    endpoint = (old.get("ollama") or {}).get("committedEndpoint", "")
    if endpoint:
        partial["ollama"] = {"committedEndpoint": endpoint}

    llm_config_service.save_config(partial)
    print(f"  config de LLM importada (segredos em modo '{mode}').")


def main():
    from app.src.db import init_db

    print("→ Criando/verificando tabelas...")
    init_db()

    print("→ Importando prompts...")
    seed_prompts()

    print("→ Garantindo prompts padrão...")
    seed_defaults()

    print("→ Importando projetos...")
    import_projects()

    print("→ Importando configuração de LLM...")
    import_llm_config()

    print("✅ Migração concluída.")


if __name__ == "__main__":
    main()
