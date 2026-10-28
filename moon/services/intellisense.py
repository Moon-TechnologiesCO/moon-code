"""IntelliSense: completions, signatures, hover docs, go to definition, symbols and diagnostics.

Python is served by Jedi (bundled). Other languages use the same language servers as VS Code,
through the LSP client in moon.services.lsp, when they're installed.
"""

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CompletionItem:
    label: str
    kind: str = "text"  # function, method, class, module, variable, property, keyword, snippet, text…
    detail: str = ""
    insert: str | None = None  # text that replaces the word being typed (defaults to label)


@dataclass(frozen=True)
class Signature:
    label: str
    parameters: list[str] = field(default_factory=list)
    active: int = 0
    doc: str = ""


@dataclass(frozen=True)
class Location:
    path: Path
    line: int  # 1-based
    column: int = 0


@dataclass(frozen=True)
class Diagnostic:
    line: int  # 0-based
    column: int
    end_line: int
    end_column: int
    message: str
    severity: str = "error"  # error, warning, info
    source: str = ""


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    line: int  # 1-based
    container: str = ""


class Provider(Protocol):
    name: str

    def complete(self, path: Path, text: str, row: int, column: int) -> list[CompletionItem]: ...
    def signature(self, path: Path, text: str, row: int, column: int) -> Signature | None: ...
    def hover(self, path: Path, text: str, row: int, column: int) -> str | None: ...
    def definition(self, path: Path, text: str, row: int, column: int) -> Location | None: ...
    def symbols(self, path: Path, text: str) -> list[Symbol]: ...
    def context(self, path: Path, text: str, row: int, column: int) -> list[str]: ...
    def diagnostics(self, path: Path, text: str) -> list[Diagnostic] | None: ...


# --- Python (Jedi) -------------------------------------------------------------

JEDI_KINDS = {"function": "function", "class": "class", "module": "module", "instance": "variable",
              "statement": "variable", "param": "variable", "keyword": "keyword", "property": "property",
              "path": "file"}


class JediProvider:
    name = "Jedi"

    def __init__(self, root: Path):
        import jedi

        self.jedi = jedi
        self.project = jedi.Project(root)

    def _script(self, path: Path, text: str):
        return self.jedi.Script(code=text, path=path, project=self.project)

    def complete(self, path, text, row, column):
        line = text.split("\n")[row] if row < text.count("\n") + 1 else ""
        prefix = re.search(r"[A-Za-z0-9_]*$", line[:column]).group(0)
        after_dot = line[: column - len(prefix)].endswith(".")
        items = []
        for index, completion in enumerate(self._script(path, text).complete(row + 1, column)):
            if completion.name.startswith("__") and not completion.name.endswith("__"):
                continue
            kind = JEDI_KINDS.get(completion.type, "text")
            if kind == "function" and after_dot:
                kind = "method"
            detail = ""
            if index < 40 and completion.type in ("function", "class"):
                signatures = completion.get_signatures()
                if signatures:
                    detail = signatures[0].to_string()
            elif completion.type in ("module",):
                detail = completion.full_name or ""
            items.append(CompletionItem(completion.name, kind, detail[:80]))
        # Private names last, like VS Code.
        items.sort(key=lambda item: item.label.startswith("_"))
        return items[:200]

    def signature(self, path, text, row, column):
        signatures = self._script(path, text).get_signatures(row + 1, column)
        if not signatures:
            return None
        first = signatures[0]
        params = [param.to_string() for param in first.params]
        return Signature(first.to_string(), params, first.index or 0, (first.docstring(raw=True) or "")[:400])

    def hover(self, path, text, row, column):
        names = self._script(path, text).help(row + 1, column)
        for name in names:
            doc = name.docstring()
            if doc:
                return doc[:1500]
        return None

    def definition(self, path, text, row, column):
        for name in self._script(path, text).goto(row + 1, column, follow_imports=True):
            if name.module_path and name.line:
                return Location(Path(name.module_path), name.line, name.column or 0)
        return None

    def symbols(self, path, text):
        result = []
        for name in self._script(path, text).get_names(all_scopes=True, definitions=True):
            if name.type in ("function", "class") or (name.type == "statement" and name.parent().type == "module"):
                parent = name.parent()
                container = parent.name if parent and parent.type in ("class", "function") else ""
                kind = "method" if name.type == "function" and container else JEDI_KINDS.get(name.type, "variable")
                result.append(Symbol(name.name, kind, name.line, container))
        return result

    def context(self, path, text, row, column):
        scope = self._script(path, text).get_context(row + 1, column)
        names = []
        while scope is not None and scope.type != "module":
            names.append(scope.name)
            scope = scope.parent()
        return list(reversed(names))

    def diagnostics(self, path, text):
        return [
            Diagnostic(error.line - 1, error.column, error.until_line - 1, error.until_column,
                       error.get_message(), "error", "syntax")
            for error in self._script(path, text).get_syntax_errors()
        ]


# --- Language servers -----------------------------------------------------------

@dataclass(frozen=True)
class ServerSpec:
    language_id: str
    command: list[str]
    install: str  # shell command that installs the server


SERVERS: dict[str, ServerSpec] = {}


def _register(extensions: str, language_id: str, command: list[str], install: str) -> None:
    for extension in extensions.split():
        SERVERS[extension] = ServerSpec(language_id, command, install)


_register(".js .mjs .cjs .jsx", "javascript", ["typescript-language-server", "--stdio"],
          "npm install -g typescript-language-server typescript")
_register(".ts .mts .tsx", "typescript", ["typescript-language-server", "--stdio"],
          "npm install -g typescript-language-server typescript")
_register(".html .htm", "html", ["vscode-html-language-server", "--stdio"], "npm install -g vscode-langservers-extracted")
_register(".css .scss", "css", ["vscode-css-language-server", "--stdio"], "npm install -g vscode-langservers-extracted")
_register(".json .jsonc", "json", ["vscode-json-language-server", "--stdio"], "npm install -g vscode-langservers-extracted")
_register(".go", "go", ["gopls"], "go install golang.org/x/tools/gopls@latest")
_register(".rs", "rust", ["rust-analyzer"], "rustup component add rust-analyzer")
_register(".c .h", "c", ["clangd"], "sudo apt install clangd")
_register(".cpp .cc .cxx .hpp", "cpp", ["clangd"], "sudo apt install clangd")
_register(".cs", "csharp", ["csharp-ls"], "dotnet tool install --global csharp-ls")
_register(".lua", "lua", ["lua-language-server"], "sudo apt install lua-language-server")
_register(".sh .bash", "shellscript", ["bash-language-server", "start"], "npm install -g bash-language-server")
_register(".php", "php", ["intelephense", "--stdio"], "npm install -g intelephense")
_register(".rb", "ruby", ["ruby-lsp"], "gem install ruby-lsp")
_register(".swift", "swift", ["sourcekit-lsp"], "xcode-select --install")
_register(".zig", "zig", ["zls"], "see https://github.com/zigtools/zls")
_register(".dart", "dart", ["dart", "language-server"], "install the Dart SDK")
_register(".kt", "kotlin", ["kotlin-language-server"], "see https://github.com/fwcd/kotlin-language-server")
_register(".yaml .yml", "yaml", ["yaml-language-server", "--stdio"], "npm install -g yaml-language-server")


def server_for(path: Path) -> ServerSpec | None:
    return SERVERS.get(path.suffix.lower())


class LspProvider:
    """Adapts an LSP client to the Provider interface for one file type."""

    def __init__(self, client, spec: ServerSpec):
        self.client = client
        self.spec = spec
        self.name = spec.command[0]

    def complete(self, path, text, row, column):
        self.client.sync(path, text, self.spec.language_id)
        return self.client.completion(path, row, column)

    def signature(self, path, text, row, column):
        self.client.sync(path, text, self.spec.language_id)
        return self.client.signature_help(path, row, column)

    def hover(self, path, text, row, column):
        self.client.sync(path, text, self.spec.language_id)
        return self.client.hover(path, row, column)

    def definition(self, path, text, row, column):
        self.client.sync(path, text, self.spec.language_id)
        return self.client.definition(path, row, column)

    def symbols(self, path, text):
        self.client.sync(path, text, self.spec.language_id)
        return self.client.document_symbols(path)

    def context(self, path, text, row, column):
        symbols = self.symbols(path, text)
        inside = [s for s in symbols if s.line <= row + 1]
        return [inside[-1].name] if inside else []

    def diagnostics(self, path, text):
        self.client.sync(path, text, self.spec.language_id)
        return None  # pushed by the server; the workspace listens to the client instead


class IntelliSense:
    """Picks the provider for each file and keeps language servers alive per project."""

    def __init__(self, root: Path, on_diagnostics=None):
        self.root = root
        self.on_diagnostics = on_diagnostics
        self._jedi: JediProvider | None = None
        self._clients: dict[tuple[str, ...], object] = {}

    def provider_for(self, path: Path) -> Provider | None:
        if path.suffix.lower() in (".py", ".pyi", ".pyw"):
            if self._jedi is None:
                try:
                    self._jedi = JediProvider(self.root)
                except ImportError:
                    return None
            return self._jedi
        spec = server_for(path)
        if spec is None or shutil.which(spec.command[0]) is None:
            return None
        key = tuple(spec.command)
        if key not in self._clients:
            from moon.services.lsp import LspClient

            client = LspClient(spec.command, self.root, self.on_diagnostics)
            try:
                client.start()
            except OSError:
                return None
            self._clients[key] = client
        return LspProvider(self._clients[key], spec)

    def missing_server(self, path: Path) -> ServerSpec | None:
        """The server this file would use, if it isn't installed."""
        spec = server_for(path)
        if spec is not None and shutil.which(spec.command[0]) is None:
            return spec
        return None

    def close_file(self, path: Path) -> None:
        for client in self._clients.values():
            client.close_file(path)

    def shutdown(self) -> None:
        for client in self._clients.values():
            client.stop()
        self._clients.clear()
