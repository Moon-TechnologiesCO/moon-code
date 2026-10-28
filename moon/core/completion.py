"""Autocomplete suggestions: words already in the file plus language keywords."""

import builtins
import keyword
import re

WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
MAX_SCAN = 300_000

KEYWORDS: dict[str, list[str]] = {
    "Python": keyword.kwlist + [name for name in dir(builtins) if not name.startswith("_")],
    "JavaScript": ["async", "await", "break", "case", "catch", "class", "const", "continue", "default",
                   "delete", "else", "export", "extends", "finally", "for", "function", "import", "let",
                   "new", "return", "static", "super", "switch", "this", "throw", "try", "typeof",
                   "while", "yield", "console", "document", "window", "Promise", "JSON", "Array", "Object"],
    "Go": ["break", "case", "chan", "const", "continue", "default", "defer", "else", "fallthrough", "for",
           "func", "go", "goto", "if", "import", "interface", "map", "package", "range", "return",
           "select", "struct", "switch", "type", "var", "string", "error", "make", "append", "len"],
    "Rust": ["as", "async", "await", "break", "const", "continue", "crate", "else", "enum", "extern",
             "false", "impl", "loop", "match", "move", "mut", "pub", "return", "self", "Self", "static",
             "struct", "trait", "true", "unsafe", "use", "where", "while", "String", "Vec", "Option",
             "Result", "println"],
    "C#": ["abstract", "async", "await", "bool", "break", "case", "catch", "class", "const", "continue",
           "decimal", "default", "double", "else", "enum", "false", "finally", "float", "foreach",
           "interface", "internal", "namespace", "new", "null", "override", "private", "protected",
           "public", "readonly", "record", "return", "static", "string", "struct", "switch", "this",
           "throw", "true", "using", "var", "virtual", "void", "while", "Console", "WriteLine"],
    "Java": ["abstract", "boolean", "break", "case", "catch", "class", "continue", "default", "double",
             "else", "enum", "extends", "final", "finally", "float", "implements", "import", "instanceof",
             "interface", "private", "protected", "public", "return", "static", "String", "super",
             "switch", "this", "throw", "throws", "void", "while", "System"],
}
KEYWORDS["TypeScript"] = KEYWORDS["JavaScript"] + ["interface", "type", "enum", "implements", "readonly",
                                                   "string", "number", "boolean", "unknown", "never"]


def suggestions(text: str, prefix: str, language: str, limit: int = 8, current: str = "") -> list[str]:
    """Candidates that start with `prefix`, most frequent words in the file first.

    `current` is the whole word under the cursor; it is never suggested back.
    """
    if len(prefix) < 2:
        return []
    lowered = prefix.lower()
    counts: dict[str, int] = {}
    for word in WORD.findall(text[:MAX_SCAN]):
        if word not in (prefix, current) and word.lower().startswith(lowered):
            counts[word] = counts.get(word, 0) + 1
    for word in KEYWORDS.get(language, []):
        if word != prefix and word.lower().startswith(lowered):
            counts.setdefault(word, 0)
    ranked = sorted(counts, key=lambda word: (-counts[word], len(word), word))
    return ranked[:limit]


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def word_before(line: str, column: int) -> str:
    """The identifier that ends at `column` in `line`."""
    start = column
    while start > 0 and _is_word_char(line[start - 1]):
        start -= 1
    return line[start:column]


def word_at(line: str, column: int) -> str:
    """The whole identifier around `column` in `line`."""
    end = column
    while end < len(line) and _is_word_char(line[end]):
        end += 1
    return word_before(line, column) + line[column:end]
