from datetime import date, datetime, timedelta, timezone

from src.collection.dates import extract_publication_date


def test_jsonld_has_highest_priority():
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type":"NewsArticle","datePublished":"2026-01-29T10:00:00-03:00"}
      </script>
      <meta property="article:published_time" content="2020-01-01"/>
    </head><body>texto</body></html>
    """
    result = extract_publication_date(html)
    assert result.value == date(2026, 1, 29)
    assert result.confidence == "high"
    assert result.method == "jsonld"


def test_opengraph_meta_is_used_when_no_jsonld():
    html = '<html><head><meta property="article:published_time" content="2025-10-30"/></head></html>'
    result = extract_publication_date(html)
    assert result.value == date(2025, 10, 30)
    assert result.confidence == "high"


def test_time_tag_is_medium_confidence():
    html = '<html><body><time datetime="2024-03-05">5 de marzo</time></body></html>'
    result = extract_publication_date(html)
    assert result.value == date(2024, 3, 5)
    assert result.confidence == "medium"


def test_spanish_text_pattern_is_low_confidence():
    result = extract_publication_date("<html><body></body></html>", "Publicado el 14 de mayo de 2026 por la redacción")
    assert result.value == date(2026, 5, 14)
    assert result.confidence == "low"


def test_absent_date_returns_none_and_does_not_invent():
    result = extract_publication_date("<html><body>sin fecha alguna</body></html>", "sin fecha alguna")
    assert result.value is None
    assert result.confidence is None
    assert result.note


def test_future_dates_are_rejected():
    future = (datetime.now(timezone.utc) + timedelta(days=400)).date().isoformat()
    html = f'<html><head><meta name="date" content="{future}"/></head></html>'
    assert extract_publication_date(html).value is None


def test_absurdly_old_dates_are_rejected():
    html = '<html><head><meta name="date" content="1901-01-01"/></head></html>'
    assert extract_publication_date(html).value is None
