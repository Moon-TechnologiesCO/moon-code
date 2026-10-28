"""Local AI client. Talks to Ollama's HTTP API."""

import json
import urllib.request
from collections.abc import Iterator

DEFAULT_URL = "http://localhost:11434"


def stream_chat(model: str, messages: list[dict], url: str = DEFAULT_URL) -> Iterator[str]:
    """Yield pieces of the reply as they arrive."""
    body = json.dumps({"model": model, "messages": messages, "stream": True}).encode()
    request = urllib.request.Request(
        f"{url}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        for line in response:
            if not line.strip():
                continue
            chunk = json.loads(line)
            yield chunk.get("message", {}).get("content", "")
            if chunk.get("done"):
                break


def list_models(url: str = DEFAULT_URL) -> list[str]:
    """Installed models, or an empty list when Ollama isn't running."""
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=3) as response:
            return [m["name"] for m in json.load(response).get("models", [])]
    except (OSError, ValueError):
        return []
