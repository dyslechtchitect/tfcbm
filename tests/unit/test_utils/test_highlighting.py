"""Tests for highlighting utilities."""


def test_highlight_text_basic():
    from ui.utils.highlighting import highlight_text

    text = "Hello World"
    query = "world"

    result = highlight_text(text, query)

    assert "yellow" in result
    assert "Hello" in result
    assert "World" in result or "world" in result


def test_highlight_text_multiple_matches():
    from ui.utils.highlighting import highlight_text

    text = "The quick brown fox jumps over the lazy dog"
    query = "the"

    result = highlight_text(text, query)

    assert result.count("yellow") == 2


def test_highlight_text_no_match():
    from ui.utils.highlighting import highlight_text

    text = "Hello World"
    query = "xyz"

    result = highlight_text(text, query)

    assert "yellow" not in result
    assert "Hello" in result
    assert "World" in result


def test_highlight_text_empty_query():
    from ui.utils.highlighting import highlight_text

    text = "Hello World"
    query = ""

    result = highlight_text(text, query)

    assert "yellow" not in result
    assert "Hello" in result


def test_highlight_text_empty_text():
    from ui.utils.highlighting import highlight_text

    text = ""
    query = "test"

    result = highlight_text(text, query)

    assert result == ""


def test_highlight_text_special_characters():
    from ui.utils.highlighting import highlight_text

    text = "Price: $50 & tax"
    query = "50"

    result = highlight_text(text, query)

    assert "yellow" in result
    assert "50" in result


def test_highlight_text_escapes_markup():
    from ui.utils.highlighting import highlight_text

    text = "<script>alert('xss')</script>"
    query = "script"

    result = highlight_text(text, query)

    assert "&lt;" in result
    assert "&gt;" in result
    assert "<script>" not in result
