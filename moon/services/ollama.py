"""Cliente de IA local para Moon Code. Habla con Ollama (http://localhost:11434)."""

import json
import os
import urllib.request
from collections.abc import Iterator

OLLAMA_URL = os.environ.get("MOON_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("MOON_MODEL", "gemma3n:e2b")


def stream_chat(model: str, messages: list[dict]) -> Iterator[str]:
    """Devuelve los trozos de texto de la respuesta según llegan."""
    body = json.dumps({"model": model, "messages": messages, "stream": True}).encode()
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        for line in response:
            if not line.strip():
                continue
            chunk = json.loads(line)
            yield chunk.get("message", {}).get("content", "")
            if chunk.get("done"):
                break


def list_models() -> list[str]:
    """Modelos instalados en Ollama, o lista vacía si el servidor no responde."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as response:
            return [m["name"] for m in json.load(response).get("models", [])]
    except OSError:
        return []
