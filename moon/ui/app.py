"""Aplicación principal de Moon Code."""

import os
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DirectoryTree, Footer, Header, Input, Static, TabbedContent, TabPane, TextArea

from moon.services import ollama as ai
from moon.core.icons import icon_for, language_for
from moon.core.themes import ALL_THEMES, EDITOR_THEMES


class MoonTree(DirectoryTree):
    """Explorador de archivos con iconos."""

    def __init__(self, path: str, nerd: bool, **kwargs):
        super().__init__(path, **kwargs)
        self.nerd = nerd

    def render_label(self, node, base_style, style) -> Text:
        path = Path(node.data.path)
        label = Text.assemble((icon_for(path, self.nerd) + " ", "bold"), (path.name, style))
        return label


class MoonEditor(TextArea):
    """Editor con números de línea, resaltado y tema Moon."""


class MoonCode(App):
    TITLE = "Moon Code"
    SUB_TITLE = "editor de terminal"
    CSS_PATH = "moon.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save", "Guardar"),
        Binding("ctrl+w", "close_tab", "Cerrar pestaña"),
        Binding("ctrl+b", "toggle_sidebar", "Explorador"),
        Binding("ctrl+t", "toggle_theme", "Tema"),
        Binding("ctrl+a", "toggle_chat", "Chat IA"),
        Binding("ctrl+q", "quit", "Salir"),
    ]

    def __init__(self, root: str = ".", nerd: bool | None = None):
        super().__init__()
        self.root_path = Path(root).resolve()
        # Nerd Font se activa con MOON_NERD=1 o con el argumento --nerd.
        self.nerd = nerd if nerd is not None else os.environ.get("MOON_NERD") == "1"
        self.open_files: dict[str, Path] = {}
        for theme in ALL_THEMES:
            self.register_theme(theme)
        self.theme = "moon-night"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace"):
            yield MoonTree(str(self.root_path), self.nerd, id="explorer")
            with TabbedContent(id="tabs"):
                yield TabPane("Bienvenida", Static(self._welcome(), id="welcome"), id="welcome-tab")
            with Vertical(id="chat"):
                yield Static(f"🌙 IA local · {ai.DEFAULT_MODEL}", id="chat-title")
                yield VerticalScroll(id="chat-log")
                yield Input(placeholder="Pregunta a la IA y pulsa Enter…", id="chat-input")
        yield Footer()

    def _welcome(self) -> str:
        return (
            "🌙  [b]Moon Code[/b]\n\n"
            "Abre un archivo desde el explorador (Enter).\n\n"
            "ctrl+s guardar · ctrl+w cerrar · ctrl+b explorador · ctrl+t tema · ctrl+p comandos · ctrl+q salir"
        )

    def on_mount(self) -> None:
        self.query_one(MoonTree).focus()

    @on(DirectoryTree.FileSelected)
    def open_file(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        key = str(path)
        tabs = self.query_one("#tabs", TabbedContent)
        if key in self.open_files:
            tabs.active = self._pane_id(key)
            return

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as error:
            self.notify(f"No se puede abrir {path.name}: {error}", severity="error")
            return

        editor = MoonEditor(
            content,
            id=self._editor_id(key),
            show_line_numbers=True,
            tab_behavior="indent",
        )
        editor.register_theme(EDITOR_THEMES["moon-night"])
        editor.theme = "moon-night"
        language = language_for(path)
        # El resaltado necesita las gramáticas de tree-sitter; sin ellas se muestra en texto plano.
        if language in editor.available_languages:
            editor.language = language
        self.open_files[key] = path
        tabs.add_pane(TabPane(f"{icon_for(path, self.nerd)} {path.name}", editor, id=self._pane_id(key)))
        tabs.active = self._pane_id(key)
        editor.focus()

    def action_save(self) -> None:
        editor = self._active_editor()
        if editor is None:
            return
        path = self.open_files[self._key_from_editor(editor)]
        path.write_text(editor.text, encoding="utf-8")
        self.notify(f"Guardado {path.name}")

    def action_close_tab(self) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        active = tabs.active
        if not active or active == "welcome-tab":
            return
        for key, path in list(self.open_files.items()):
            if self._pane_id(key) == active:
                del self.open_files[key]
                break
        tabs.remove_pane(active)

    def action_toggle_sidebar(self) -> None:
        tree = self.query_one(MoonTree)
        tree.display = not tree.display
        if tree.display:
            tree.focus()

    def action_toggle_theme(self) -> None:
        self.theme = "moon-light" if self.theme == "moon-night" else "moon-night"

    def action_toggle_chat(self) -> None:
        chat = self.query_one("#chat", Vertical)
        chat.display = not chat.display
        if chat.display:
            self.query_one("#chat-input", Input).focus()

    @on(Input.Submitted, "#chat-input")
    def send_to_ai(self, event: Input.Submitted) -> None:
        question = event.value.strip()
        event.input.value = ""
        if not question:
            return
        log = self.query_one("#chat-log", VerticalScroll)
        log.mount(Static(f"[b]Tú:[/b] {question}", classes="msg"))
        reply = Static("…", classes="msg reply")
        log.mount(reply)
        self._ask_ai(question, reply)

    @work(thread=True, exclusive=True)
    def _ask_ai(self, question: str, reply: Static) -> None:
        messages = [{"role": "user", "content": question}]
        text = ""
        try:
            for piece in ai.stream_chat(ai.DEFAULT_MODEL, messages):
                text += piece
                self.call_from_thread(reply.update, text)
        except OSError as error:
            text = f"No pude conectar con Ollama en {ai.OLLAMA_URL}: {error}"
            self.call_from_thread(reply.update, text)
        self.call_from_thread(self.query_one("#chat-log", VerticalScroll).scroll_end)

    def _active_editor(self) -> MoonEditor | None:
        tabs = self.query_one("#tabs", TabbedContent)
        for key in self.open_files:
            if self._pane_id(key) == tabs.active:
                return self.query_one(f"#{self._editor_id(key)}", MoonEditor)
        return None

    def _key_from_editor(self, editor: MoonEditor) -> str:
        for key in self.open_files:
            if self._editor_id(key) == editor.id:
                return key
        raise KeyError(editor.id)

    @staticmethod
    def _pane_id(key: str) -> str:
        return "pane-" + _slug(key)

    @staticmethod
    def _editor_id(key: str) -> str:
        return "editor-" + _slug(key)


def _slug(text: str) -> str:
    """Convierte una ruta en un id válido para Textual."""
    return "".join(ch if ch.isalnum() else "_" for ch in text)


def run(argv: list[str]) -> None:
    nerd = "--nerd" in argv
    args = [a for a in argv if a != "--nerd"]
    MoonCode(args[0] if args else ".", nerd=nerd).run()
