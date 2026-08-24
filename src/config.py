"""Carga de configuración desde YAML + variables de entorno.

Toda la configuración editable por el equipo vive en `config/*.yaml`.
Los secretos viven en `.env` y nunca se versionan.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Falta el archivo de configuración: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def themes_config() -> dict[str, Any]:
    return _load_yaml("themes.yaml")


@lru_cache(maxsize=1)
def sources_config() -> dict[str, Any]:
    return _load_yaml("sources.yaml")


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    return _load_yaml("settings.yaml")


def all_themes() -> list[dict[str, str]]:
    """Temáticas núcleo y adyacentes con su relación temática declarada."""
    cfg = themes_config()
    out: list[dict[str, str]] = []
    for theme in cfg.get("core_themes", []):
        out.append({**theme, "default_relation": "core"})
    for theme in cfg.get("adjacent_themes", []):
        out.append({**theme, "default_relation": "adjacent"})
    return out


def theme_names() -> list[str]:
    return [t["name"] for t in all_themes()]


def project_description() -> str:
    return (themes_config().get("project", {}) or {}).get("description", "").strip()


def core_topic() -> str:
    return (themes_config().get("project", {}) or {}).get("core_topic", "").strip()


def source_registry() -> dict[str, dict[str, Any]]:
    """Índice dominio -> metadata de fuente, para resolver nombre editorial y owner."""
    registry: dict[str, dict[str, Any]] = {}
    for src in sources_config().get("sources", []):
        registry.setdefault(src["domain"], src)
    return registry


def database_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return os.getenv("DATABASE_URL") or f"sqlite:///{DATA_DIR / 'senales.db'}"
