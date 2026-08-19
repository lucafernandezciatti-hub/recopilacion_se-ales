"""Capa abstracta de proveedor de IA.

La aplicación no se acopla a ninguna API concreta. Hoy: Anthropic, OpenAI y un
proveedor mock que permite correr todo el pipeline sin API key.
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from src.ai.prompts import (
    SIGNAL_CLASSIFIER_SYSTEM,
    SIGNAL_CLASSIFIER_USER,
    SIGNAL_CLASSIFIER_VERSION,
)
from src.config import all_themes, core_topic, project_description
from src.signals.schemas import SignalAnalysis
from src.signals.validation import validate_quote

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
MAX_ARTICLE_CHARS = 14000


@dataclass(slots=True)
class AnalysisResult:
    analysis: SignalAnalysis | None
    model: str
    prompt_version: str
    error: str | None = None
    quote_valid: bool = False


def _themes_block() -> str:
    lines = []
    for theme in all_themes():
        relation = "núcleo" if theme["default_relation"] == "core" else "adyacente"
        desc = " ".join(theme.get("description", "").split())
        lines.append(f"- {theme['name']} [{relation}]: {desc}")
    return "\n".join(lines)


def build_user_prompt(article: dict[str, Any]) -> str:
    return SIGNAL_CLASSIFIER_USER.format(
        project_description=project_description(),
        core_topic=core_topic(),
        themes_block=_themes_block(),
        source_name=article.get("source_name") or "?",
        source_domain=article.get("source_domain") or "?",
        publication_date=article.get("publication_date") or "desconocida",
        original_title=article.get("original_title") or "?",
        url=article.get("url") or "?",
        article_text=(article.get("cleaned_text") or "")[:MAX_ARTICLE_CHARS],
    )


def parse_analysis(raw: str) -> SignalAnalysis:
    """Recuperación controlada: si no es JSON puro, se busca el primer objeto."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if not match:
            raise ValueError("la respuesta no contiene JSON")
        payload = json.loads(match.group(0))
    return SignalAnalysis.model_validate(payload)


class AIProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...

    def analyze_signal(self, article: dict[str, Any]) -> AnalysisResult:
        """Clasifica un artículo y verifica la cita contra el texto real."""
        try:
            raw = self.complete(SIGNAL_CLASSIFIER_SYSTEM, build_user_prompt(article))
        except Exception as exc:  # la app nunca cae por un fallo del proveedor
            logger.warning("fallo del proveedor de IA: %s", exc)
            return AnalysisResult(None, self.name, SIGNAL_CLASSIFIER_VERSION, str(exc))

        try:
            analysis = parse_analysis(raw)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            return AnalysisResult(
                None, self.name, SIGNAL_CLASSIFIER_VERSION, f"salida inválida: {exc}"
            )

        valid = validate_quote(article.get("cleaned_text") or "", analysis.quote)
        if not valid:
            return AnalysisResult(
                analysis,
                self.name,
                SIGNAL_CLASSIFIER_VERSION,
                "la cita no aparece literalmente en el artículo: salida rechazada",
                quote_valid=False,
            )
        return AnalysisResult(analysis, self.name, SIGNAL_CLASSIFIER_VERSION, None, True)


class AnthropicProvider(AIProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        import anthropic  # import diferido: la dependencia es opcional

        self.name = model or os.getenv("AI_MODEL", "claude-sonnet-4-5")
        self._client = anthropic.Anthropic(api_key=api_key or os.getenv("AI_API_KEY"))

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self.name,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class OpenAIProvider(AIProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI  # import diferido

        self.name = model or os.getenv("AI_MODEL", "gpt-4.1-mini")
        self._client = OpenAI(api_key=api_key or os.getenv("AI_API_KEY"))

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


class MockProvider(AIProvider):
    """Permite ejercitar el pipeline completo sin API key.

    Toma como cita el párrafo más largo del artículo, con lo cual la validación
    literal siempre pasa; el resto de los campos son heurísticos y quedan
    marcados como propuestas de baja confianza.
    """

    name = "mock"

    def complete(self, system: str, user: str) -> str:  # pragma: no cover
        raise NotImplementedError("MockProvider sobreescribe analyze_signal")

    def analyze_signal(self, article: dict[str, Any]) -> AnalysisResult:
        text = article.get("cleaned_text") or ""
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) >= 120]
        quote = (paragraphs[0] if paragraphs else text[:400]).strip()[:600]
        themes = all_themes()
        theme = themes[0] if themes else {"name": "Sin clasificar", "default_relation": "core"}
        analysis = SignalAnalysis(
            signal_title=(article.get("original_title") or "Señal sin título")[:250],
            theme=theme["name"],
            thematic_relation=theme["default_relation"],
            steep="Social",
            relevance=5,
            suggested_utility="useful",
            why_it_matters_suggestion=(
                "Propuesta automática de prueba (proveedor mock): requiere reemplazo "
                "por un juicio humano o por un proveedor de IA real."
            ),
            short_reasoning="Salida generada por el proveedor mock, sin análisis real.",
            quote=quote,
        )
        valid = validate_quote(text, analysis.quote)
        return AnalysisResult(analysis, self.name, SIGNAL_CLASSIFIER_VERSION, None, valid)


def get_provider(name: str | None = None) -> AIProvider:
    provider = (name or os.getenv("AI_PROVIDER", "mock")).lower()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"proveedor de IA desconocido: {provider}")
