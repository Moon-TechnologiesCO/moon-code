"""Floating IntelliSense widgets: suggestion list, signature help and hover card."""

from rich.text import Text
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from moon.services.intellisense import CompletionItem, Signature

# Kind icons and colors, like VS Code's suggest widget (Nerd Font codicons / Material icons).
KIND_ICONS: dict[str, tuple[str, str, str]] = {  # kind -> (nerd glyph, plain glyph, color)
    "method": ("\U000f01a7", "m", "#b180d7"),
    "function": ("\U000f0295", "ƒ", "#b180d7"),
    "class": ("\U000f0831", "C", "#ee9d28"),
    "interface": ("", "I", "#75beff"),
    "module": ("", "M", "#cccccc"),
    "variable": ("\U000f002b", "v", "#75beff"),
    "property": ("\U000f0722", "p", "#75beff"),
    "constant": ("\U000f03ff", "c", "#ee9d28"),
    "enum": ("", "E", "#ee9d28"),
    "value": ("\U000f03a0", "=", "#ee9d28"),
    "keyword": ("\U000f030b", "k", "#cccccc"),
    "snippet": ("", "s", "#cccccc"),
    "file": ("\U000f0219", "f", "#cccccc"),
    "text": ("\U000f027f", "t", "#8a93b8"),
}


def kind_icon(kind: str, nerd: bool) -> Text:
    glyph, plain, color = KIND_ICONS.get(kind, KIND_ICONS["text"])
    return Text(glyph if nerd else plain, style=f"bold {color}")


class CompletionMenu(OptionList, can_focus=False):
    """Suggestion list. Keys stay with the editor, so it never takes focus."""

    def show_items(self, items: list[CompletionItem], prefix: str, nerd: bool) -> int:
        """Fill the list and return the width it needs."""
        self.clear_options()
        width = 24
        for item in items:
            line = Text.assemble(kind_icon(item.kind, nerd), " ")
            label = Text(item.label)
            if prefix and item.label.lower().startswith(prefix.lower()):
                label.stylize("bold", 0, len(prefix))
            line.append_text(label)
            if item.detail:
                detail = item.detail if len(item.detail) <= 48 else item.detail[:47] + "…"
                line.append(f"  {detail}", style="dim")
            width = max(width, line.cell_len + 3)
            self.add_option(Option(line))
        self.highlighted = 0 if items else None
        return min(width, 80)


class SignatureHint(Static):
    """Parameter hints above the cursor while typing a call: `fibonacci(count: int)`."""

    def show_signature(self, signature: Signature) -> None:
        text = Text(signature.label)
        if signature.parameters and 0 <= signature.active < len(signature.parameters):
            param = signature.parameters[signature.active]
            start = signature.label.find(param)
            if start >= 0:
                text.stylize("bold underline", start, start + len(param))
        doc = signature.doc.strip().split("\n")[0] if signature.doc else ""
        if doc:
            text.append(f"\n{doc[:100]}", style="dim")
        self.update(text)


class HoverCard(Static):
    """Docs and problems for the symbol under the mouse."""
