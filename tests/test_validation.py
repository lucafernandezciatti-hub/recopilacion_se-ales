from src.signals.validation import find_quote_offset, quote_length_ok, validate_quote

ARTICLE = (
    "El Ministerio informó los resultados. "
    "La matrícula del nivel primario en la Argentina experimentará una caída del 27% para 2030, "
    "lo que equivale a 1,2 millones de estudiantes menos en comparación con 2023. "
    "Los especialistas advierten sobre el impacto en la infraestructura escolar."
)


def test_exact_quote_is_valid():
    quote = "La matrícula del nivel primario en la Argentina experimentará una caída del 27% para 2030"
    assert validate_quote(ARTICLE, quote)


def test_whitespace_differences_are_tolerated():
    quote = "La  matrícula   del nivel primario\nen la Argentina experimentará una caída del 27%"
    assert validate_quote(ARTICLE, quote)


def test_typographic_quotes_and_dashes_are_normalized():
    article = 'Dijo: “la escuela cambió” —afirmó— durante el acto.'
    assert validate_quote(article, 'Dijo: "la escuela cambió" -afirmó- durante el acto.')


def test_paraphrase_is_rejected():
    quote = "La matrícula primaria caerá un 27 por ciento hacia 2030"
    assert not validate_quote(ARTICLE, quote)


def test_invented_quote_is_rejected():
    assert not validate_quote(ARTICLE, "El ministro renunció esta mañana tras el escándalo.")


def test_empty_inputs_are_rejected():
    assert not validate_quote("", "algo")
    assert not validate_quote(ARTICLE, "")


def test_elided_quote_with_long_fragments_is_accepted():
    quote = (
        "La matrícula del nivel primario en la Argentina experimentará una caída del 27% "
        "... lo que equivale a 1,2 millones de estudiantes menos en comparación con 2023"
    )
    assert validate_quote(ARTICLE, quote)


def test_elided_quote_out_of_order_is_rejected():
    quote = (
        "lo que equivale a 1,2 millones de estudiantes menos en comparación con 2023 "
        "... La matrícula del nivel primario en la Argentina experimentará una caída"
    )
    assert not validate_quote(ARTICLE, quote)


def test_quote_length_bounds():
    assert not quote_length_ok("corta")
    assert quote_length_ok("x" * 100)
    assert not quote_length_ok("x" * 1000)


def test_find_offset():
    assert find_quote_offset(ARTICLE, "El Ministerio informó") == 0
    assert find_quote_offset(ARTICLE, "no está") is None
