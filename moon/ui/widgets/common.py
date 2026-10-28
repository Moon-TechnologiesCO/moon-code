"""Small building blocks shared by the views."""

from textual import events
from textual.widgets import Static


class Clickable(Static):
    """Text that runs an action when clicked, e.g. "screen.toggle_sidebar"."""

    def __init__(self, label: str, action: str, tooltip: str | None = None, **kwargs):
        super().__init__(label, **kwargs)
        self.action = action
        if tooltip:
            self.tooltip = tooltip

    async def on_click(self, event: events.Click) -> None:
        event.stop()
        await self.app.run_action(self.action, self.screen)


class SectionTitle(Static):
    """Uppercase heading at the top of a side view (EXPLORER, SEARCH…)."""
