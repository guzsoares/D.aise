"""
Models ORM (SQLAlchemy) que mapeiam as tabelas do PostgreSQL.

Estes são propositalmente separados das classes de domínio (`model/project_model.py`,
`model/prompt_model.py`), que mantêm suas assinaturas atuais e delegam a
persistência para cá.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.src.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # chave de lookup usada em todo o código (controllers/services)
    folder_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, default="")
    path: Mapped[str] = mapped_column(Text, default="")
    tree: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    readme: Mapped[str] = mapped_column(Text, default="")
    changelog: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(Text, default="")
    framework: Mapped[str] = mapped_column(Text, default="")
    dependence_file_name: Mapped[str] = mapped_column(Text, default="")
    main_file: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[str] = mapped_column(Text, default="")
    commits: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String, default="local")
    github_repo: Mapped[str] = mapped_column(Text, default="")
    # Guarda campos que não têm coluna dedicada (ex.: has_readme), preservando a
    # flexibilidade do JSON antigo sem perda de dados.
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Campos do domínio que NÃO são colunas (são @property que leem do disco):
    #   dependence_file_content, readme_content
    COLUMNS = (
        "id", "folder_name", "name", "path", "tree", "description", "readme",
        "changelog", "language", "framework", "dependence_file_name",
        "main_file", "diff", "commits", "source", "github_repo",
    )

    def to_dict(self) -> dict:
        return {c: getattr(self, c) for c in self.COLUMNS}


class PromptRow(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "content": self.content,
            "is_active": self.is_active,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class DefaultPromptRow(Base):
    __tablename__ = "default_prompts"

    # 1 default por tipo (analyze_project | create_readme | update_readme)
    type: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True
    )


class LlmConfigRow(Base):
    """Config de LLM em linha única (id fixo = 1), guardada como JSONB.

    Segredos guardados no modo 'cloud' ficam CRIPTOGRAFADOS dentro deste JSON;
    segredos no modo 'local' não ficam aqui (ficam em arquivo no host).
    """
    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
