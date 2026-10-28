from moon.core.completion import suggestions, word_at, word_before


def test_suggests_words_from_file_by_frequency():
    text = "render render renderer"
    assert suggestions(text, "re", "Plain Text") == ["render", "renderer"]


def test_includes_language_keywords():
    assert "return" in suggestions("", "ret", "Python")


def test_never_suggests_the_word_being_typed():
    assert "greprint" not in suggestions("greet greprint", "gre", "Plain Text", current="greprint")


def test_short_prefix_gives_nothing():
    assert suggestions("hello", "h", "Plain Text") == []


def test_word_helpers():
    assert word_before("foo.bar_baz", 11) == "bar_baz"
    assert word_at("print(value)", 8) == "value"
