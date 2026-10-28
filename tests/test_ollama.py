import json

from moon.services import ollama


class FakeResponse(list):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_stream_chat_yields_text_until_done(monkeypatch):
    lines = [
        json.dumps({"message": {"content": "Hola"}, "done": False}).encode(),
        json.dumps({"message": {"content": " mundo"}, "done": True}).encode(),
    ]
    monkeypatch.setattr(ollama.urllib.request, "urlopen", lambda *a, **k: FakeResponse(lines))
    assert "".join(ollama.stream_chat("modelo", [])) == "Hola mundo"


def test_list_models_returns_empty_when_offline(monkeypatch):
    def offline(*a, **k):
        raise OSError("sin servidor")

    monkeypatch.setattr(ollama.urllib.request, "urlopen", offline)
    assert ollama.list_models() == []
