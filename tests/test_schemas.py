import pytest
from pydantic import ValidationError

from src.ai.provider import parse_analysis
from src.signals.schemas import SignalAnalysis

VALID = {
    "signal_title": "Los asistentes de IA se integran a plataformas escolares",
    "theme": "IA y tecnologías de aprendizaje",
    "thematic_relation": "adjacent",
    "steep": "Technological",
    "relevance": 8,
    "suggested_utility": "useful",
    "why_it_matters_suggestion": "Si estas herramientas se masifican, la evaluación podría volverse continua.",
    "short_reasoning": "Está en tema y abre una posibilidad concreta.",
    "quote": "La inteligencia artificial ya es parte de nuestras vidas y la escuela debe enseñarla.",
}


def test_valid_payload():
    analysis = SignalAnalysis.model_validate(VALID)
    assert analysis.relevance == 8


@pytest.mark.parametrize("relevance", [0, 11, -3])
def test_relevance_out_of_range_is_rejected(relevance):
    with pytest.raises(ValidationError):
        SignalAnalysis.model_validate({**VALID, "relevance": relevance})


def test_unknown_steep_is_rejected():
    with pytest.raises(ValidationError):
        SignalAnalysis.model_validate({**VALID, "steep": "Cultural"})


def test_unknown_utility_is_rejected():
    with pytest.raises(ValidationError):
        SignalAnalysis.model_validate({**VALID, "suggested_utility": "muy_util"})


def test_unknown_relation_is_rejected():
    with pytest.raises(ValidationError):
        SignalAnalysis.model_validate({**VALID, "thematic_relation": "peripheral"})


def test_shouty_title_is_rejected():
    with pytest.raises(ValidationError):
        SignalAnalysis.model_validate({**VALID, "signal_title": "GOOGLE PRESENTA HERRAMIENTA"})


def test_parse_analysis_handles_markdown_fences():
    raw = "```json\n" + SignalAnalysis.model_validate(VALID).model_dump_json() + "\n```"
    assert parse_analysis(raw).theme == VALID["theme"]


def test_parse_analysis_handles_surrounding_prose():
    payload = SignalAnalysis.model_validate(VALID).model_dump_json()
    raw = f"Claro, acá está el análisis:\n{payload}\nEspero que sirva."
    assert parse_analysis(raw).relevance == 8


def test_parse_analysis_raises_without_json():
    with pytest.raises(ValueError):
        parse_analysis("no hay json acá")
