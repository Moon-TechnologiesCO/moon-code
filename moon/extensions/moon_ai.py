"""Moon AI: the chat view lives in the workspace; this adds its commands."""


def activate(api) -> None:
    # The workspace implements these two; the extension only exposes them as commands.
    api.add_command("AI: Open Chat", "Open the Moon AI chat (ctrl+l)", api.open_ai_chat)
    api.add_command("AI: Explain Active File", "Ask the local model to explain the active file", api.explain_active_file)
