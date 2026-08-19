import pytest

from src.collection.normalize import domain_of, normalize_url, text_hash, url_hash


def test_removes_tracking_params_and_fragment():
    url = "http://www.lanacion.com.ar/sociedad/nota-123/?utm_source=twitter&id=7#comentarios"
    assert normalize_url(url) == "https://lanacion.com.ar/sociedad/nota-123?id=7"


def test_forces_https_and_strips_www():
    assert normalize_url("http://www.infobae.com/educacion/") == "https://infobae.com/educacion"


def test_adds_scheme_when_missing():
    assert normalize_url("chequeado.com/nota").startswith("https://chequeado.com")


def test_same_article_different_tracking_gives_same_hash():
    a = "https://infobae.com/educacion/nota?utm_campaign=x"
    b = "https://www.infobae.com/educacion/nota/?fbclid=abc"
    assert url_hash(a) == url_hash(b)


def test_different_articles_give_different_hash():
    assert url_hash("https://a.com/uno") != url_hash("https://a.com/dos")


def test_query_order_does_not_matter():
    assert url_hash("https://a.com/x?b=2&a=1") == url_hash("https://a.com/x?a=1&b=2")


def test_domain_of():
    assert domain_of("https://www.Pagina12.com.ar/nota") == "pagina12.com.ar"


@pytest.mark.parametrize("bad", ["", "   ", "ftp://x.com/a", "https://"])
def test_invalid_urls_raise(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


def test_text_hash_ignores_whitespace_and_case():
    a = "  Hola   Mundo. " + "x" * 300
    b = "hola mundo. " + "x" * 300
    assert text_hash(a) == text_hash(b)


def test_text_hash_none_for_short_text():
    assert text_hash("muy corto") is None
