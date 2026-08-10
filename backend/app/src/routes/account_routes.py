"""
Opções do usuário: limpeza dos próprios dados (privacidade).

Todas as ações operam sobre o usuário autenticado (Bearer token).
"""
from flask import Blueprint, jsonify

from app.src.service import llm_config_service

account_bp = Blueprint("account", __name__)


@account_bp.route("/credentials", methods=["DELETE"])
def clear_credentials():
    """Apaga todas as credenciais (chaves/tokens) do usuário — banco e arquivo local."""
    removed = llm_config_service.clear_credentials()
    return jsonify({
        "message": "Credenciais removidas.",
        "removed": removed,
    }), 200
