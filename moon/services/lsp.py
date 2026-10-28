"""A small Language Server Protocol client (the protocol VS Code uses for IntelliSense).

Runs the server as a subprocess, talks JSON-RPC over stdin/stdout from a reader thread and
exposes blocking calls with a timeout, so the UI can call them from worker threads.
"""

import itertools
import json
import os
import re
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from moon.services.intellisense import CompletionItem, Diagnostic, Location, Signature, Symbol

COMPLETION_KINDS = {1: "text", 2: "method", 3: "function", 4: "function", 5: "property", 6: "variable",
                    7: "class", 8: "interface", 9: "module", 10: "property", 12: "value", 13: "enum",
                    14: "keyword", 15: "snippet", 17: "file", 20: "enum", 21: "constant", 22: "class",
                    25: "class"}
SYMBOL_KINDS = {2: "module", 5: "class", 6: "method", 7: "property", 8: "property", 9: "function",
                10: "enum", 11: "interface", 12: "function", 13: "variable", 14: "constant", 23: "class"}
SEVERITIES = {1: "error", 2: "warning", 3: "info", 4: "info"}
SNIPPET_FIELD = re.compile(r"\$\{\d+(?::([^}]*))?\}|\$\d+")


def path_uri(path: Path) -> str:
    return Path(path).resolve().as_uri()


def uri_path(uri: str) -> Path:
    return Path(unquote(urlparse(uri).path))


def _plain(snippet: str) -> str:
    """Turn an LSP snippet like `print(${1:value})$0` into plain text."""
    return SNIPPET_FIELD.sub(lambda match: match.group(1) or "", snippet)


def _markup_text(contents) -> str:
    if isinstance(contents, str):
        return contents
    if isinstance(contents, dict):
        return contents.get("value", "")
    if isinstance(contents, list):
        return "\n\n".join(_markup_text(item) for item in contents)
    return ""


class LspClient:
    def __init__(self, command: list[str], root: Path, on_diagnostics=None, timeout: float = 4.0):
        self.command = command
        self.root = Path(root)
        self.on_diagnostics = on_diagnostics
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, tuple[threading.Event, list]] = {}
        self._lock = threading.Lock()
        self._documents: dict[Path, tuple[int, str]] = {}  # path -> (version, text)
        self.capabilities: dict = {}

    # --- Process & transport ------------------------------------------------

    def start(self) -> None:
        self.process = subprocess.Popen(
            self.command, cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=dict(os.environ),
        )
        threading.Thread(target=self._read_loop, daemon=True).start()
        result = self.request("initialize", {
            "processId": os.getpid(),
            "rootUri": path_uri(self.root),
            "workspaceFolders": [{"uri": path_uri(self.root), "name": self.root.name}],
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True},
                    "completion": {"completionItem": {"snippetSupport": False, "documentationFormat": ["plaintext"]}},
                    "hover": {"contentFormat": ["plaintext", "markdown"]},
                    "signatureHelp": {"signatureInformation": {"documentationFormat": ["plaintext"]}},
                    "definition": {},
                    "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                    "publishDiagnostics": {},
                },
                "workspace": {"configuration": True, "workspaceFolders": True},
            },
        }, timeout=20)
        self.capabilities = (result or {}).get("capabilities", {})
        self.notify("initialized", {})

    def _send(self, message: dict) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        body = json.dumps(message).encode()
        with self._lock:
            try:
                self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def _read_loop(self) -> None:
        stream = self.process.stdout
        while True:
            length = 0
            while True:
                line = stream.readline()
                if not line:
                    return
                line = line.strip()
                if not line:
                    break
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
            if not length:
                continue
            try:
                message = json.loads(stream.read(length))
            except ValueError:
                continue
            self._dispatch(message)

    def _dispatch(self, message: dict) -> None:
        if "id" in message and ("result" in message or "error" in message):
            waiter = self._pending.pop(message["id"], None)
            if waiter:
                waiter[1].append(message.get("result"))
                waiter[0].set()
        elif "id" in message and "method" in message:
            # Requests from the server (configuration, progress…): answer so it never waits on us.
            result = [None] * len(message.get("params", {}).get("items", [])) if message["method"] == "workspace/configuration" else None
            self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        elif message.get("method") == "textDocument/publishDiagnostics" and self.on_diagnostics:
            params = message["params"]
            diagnostics = [
                Diagnostic(d["range"]["start"]["line"], d["range"]["start"]["character"],
                           d["range"]["end"]["line"], d["range"]["end"]["character"],
                           d.get("message", ""), SEVERITIES.get(d.get("severity", 1), "error"), str(d.get("source", "")))
                for d in params.get("diagnostics", [])
            ]
            self.on_diagnostics(uri_path(params["uri"]), diagnostics)

    def request(self, method: str, params: dict, timeout: float | None = None):
        request_id = next(self._ids)
        event, box = threading.Event(), []
        self._pending[request_id] = (event, box)
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        if not event.wait(timeout or self.timeout):
            self._pending.pop(request_id, None)
            return None
        return box[0] if box else None

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.request("shutdown", {}, timeout=1)
            self.notify("exit", {})
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()

    # --- Documents ----------------------------------------------------------

    def sync(self, path: Path, text: str, language_id: str) -> None:
        path = Path(path).resolve()
        known = self._documents.get(path)
        if known is None:
            self._documents[path] = (1, text)
            self.notify("textDocument/didOpen", {"textDocument": {
                "uri": path_uri(path), "languageId": language_id, "version": 1, "text": text}})
        elif known[1] != text:
            version = known[0] + 1
            self._documents[path] = (version, text)
            self.notify("textDocument/didChange", {
                "textDocument": {"uri": path_uri(path), "version": version},
                "contentChanges": [{"text": text}]})

    def close_file(self, path: Path) -> None:
        path = Path(path).resolve()
        if self._documents.pop(path, None) is not None:
            self.notify("textDocument/didClose", {"textDocument": {"uri": path_uri(path)}})

    def _position(self, path: Path, row: int, column: int) -> dict:
        return {"textDocument": {"uri": path_uri(path)}, "position": {"line": row, "character": column}}

    # --- Features -----------------------------------------------------------

    def completion(self, path: Path, row: int, column: int) -> list[CompletionItem]:
        result = self.request("textDocument/completion", self._position(path, row, column))
        items = result.get("items", []) if isinstance(result, dict) else (result or [])
        completions = []
        for item in items[:200]:
            edit = item.get("textEdit") or {}
            insert = edit.get("newText") or item.get("insertText") or item["label"]
            if item.get("insertTextFormat") == 2:
                insert = _plain(insert)
            completions.append(CompletionItem(
                item["label"].strip(), COMPLETION_KINDS.get(item.get("kind", 1), "text"),
                (item.get("detail") or "")[:80], insert.strip()))
        completions.sort(key=lambda c: next((i.get("sortText") or c.label for i in items if i["label"].strip() == c.label), c.label))
        return completions

    def signature_help(self, path: Path, row: int, column: int) -> Signature | None:
        result = self.request("textDocument/signatureHelp", self._position(path, row, column))
        if not result or not result.get("signatures"):
            return None
        index = result.get("activeSignature") or 0
        signature = result["signatures"][min(index, len(result["signatures"]) - 1)]
        params = []
        for param in signature.get("parameters", []):
            label = param.get("label", "")
            if isinstance(label, list):
                label = signature["label"][label[0]:label[1]]
            params.append(label)
        active = result.get("activeParameter", signature.get("activeParameter", 0)) or 0
        return Signature(signature["label"], params, active, _markup_text(signature.get("documentation", ""))[:400])

    def hover(self, path: Path, row: int, column: int) -> str | None:
        result = self.request("textDocument/hover", self._position(path, row, column))
        text = _markup_text(result.get("contents")) if result else ""
        return text.strip() or None

    def definition(self, path: Path, row: int, column: int) -> Location | None:
        result = self.request("textDocument/definition", self._position(path, row, column))
        if isinstance(result, list):
            result = result[0] if result else None
        if not result:
            return None
        uri = result.get("uri") or result.get("targetUri")
        target = result.get("range") or result.get("targetSelectionRange") or result.get("targetRange")
        start = target["start"]
        return Location(uri_path(uri), start["line"] + 1, start["character"])

    def document_symbols(self, path: Path) -> list[Symbol]:
        result = self.request("textDocument/documentSymbol", {"textDocument": {"uri": path_uri(path)}}) or []
        symbols: list[Symbol] = []

        def walk(items, container=""):
            for item in items:
                start = (item.get("selectionRange") or item.get("range") or item.get("location", {}).get("range"))["start"]
                symbols.append(Symbol(item["name"], SYMBOL_KINDS.get(item.get("kind"), "variable"),
                                      start["line"] + 1, container or item.get("containerName", "")))
                walk(item.get("children", []), item["name"])

        walk(result)
        return sorted(symbols, key=lambda symbol: symbol.line)
