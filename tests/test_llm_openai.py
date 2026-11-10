"""OpenAI 호환 방식(gemini · ollama · openai): 표준 라이브러리로 chat/completions를 부른다."""
import io
import json
import urllib.error
import urllib.request

import pytest

from server import llm


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _answer(text):
    return FakeResp(json.dumps({"choices": [{"message": {"content": text}}]}).encode())


def test_gemini_defaults_and_think_stripping(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MALHAN_AI", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    seen = {}

    def fake_open(req, timeout=0):
        seen["url"] = req.full_url; seen["auth"] = req.get_header("Authorization"); seen["body"] = json.loads(req.data)
        return _answer("<think>생각</think>[{\"text\": \"우유 사기\"}]")
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    assert llm.mode() == "gemini"
    assert llm.complete("녹음 내용: 우유 사야 해") == '[{"text": "우유 사기"}]'
    assert seen["url"].startswith("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
    assert seen["auth"] == "Bearer g-key" and seen["body"]["model"] == "gemini-3.8-flash" and seen["body"]["reasoning_effort"] == "low"


def test_gemini_key_autodetect(monkeypatch):
    monkeypatch.delenv("MALHAN_AI", raising=False); monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.delenv("MALHAN_FAKE_LLM", raising=False)
    monkeypatch.setattr(llm, "_claude_bin", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert llm.mode() == "gemini"
    monkeypatch.delenv("GEMINI_API_KEY")
    assert llm.mode() == "none"


def test_ollama_errors_are_readable(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "ollama")
    monkeypatch.setenv("MALHAN_OLLAMA_MODEL", "qwen3:8b")

    def not_running(req, timeout=0):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", not_running)
    with pytest.raises(llm.LlmUnavailable, match="ollama serve"):
        llm.complete("x")

    def no_model(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b"model not found"))
    monkeypatch.setattr(urllib.request, "urlopen", no_model)
    with pytest.raises(llm.LlmUnavailable, match="ollama pull qwen3:8b"):
        llm.complete("x")
    assert llm.openai_config("ollama")[0] == "http://localhost:11434/v1"


def test_openai_generic_needs_config(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "openai")
    monkeypatch.delenv("MALHAN_OPENAI_BASE_URL", raising=False); monkeypatch.delenv("MALHAN_OPENAI_MODEL", raising=False)
    with pytest.raises(llm.LlmUnavailable, match="MALHAN_OPENAI_BASE_URL"):
        llm.complete("x")


def test_rate_limit_message(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("MALHAN_GEMINI_FALLBACK", raising=False)
    monkeypatch.setattr("time.sleep", lambda s: None)
    def limited(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 429, "too many", {}, io.BytesIO(b"quota"))
    monkeypatch.setattr(urllib.request, "urlopen", limited)
    with pytest.raises(llm.LlmUnavailable, match="한도"):
        llm.complete("x")


def test_retries_with_model_google_suggests(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.setenv("MALHAN_GEMINI_MODEL", "gemini-old")
    models = []
    def fake(req, timeout=0):
        models.append(json.loads(req.data)["model"])
        if len(models) == 1:
            msg = b'{"error":{"code":404,"message":"This model models/gemini-old is no longer available to new users. Please update your code to use models/gemini-new for the latest features"}}'
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(msg))
        return _answer("ok")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert llm.complete("x") == "ok" and models == ["gemini-old", "gemini-new"]
    assert llm.suggested_model("no hint here") == ""


def test_drops_reasoning_effort_if_server_rejects_it(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k")
    bodies = []
    def fake(req, timeout=0):
        bodies.append(json.loads(req.data))
        if "reasoning_effort" in bodies[-1]:
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b'{"error":{"message":"Unknown name reasoning_effort"}}'))
        return _answer("ok")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert llm.complete("x") == "ok" and len(bodies) == 2 and "reasoning_effort" not in bodies[1]


def test_503_waits_then_retries_then_fallback(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.setenv("MALHAN_GEMINI_FALLBACK", "gemini-lite")
    monkeypatch.setattr("time.sleep", lambda s: None)
    models = []
    def fake(req, timeout=0):
        models.append(json.loads(req.data)["model"])
        if models[-1] != "gemini-lite":
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b'{"error":{"status":"UNAVAILABLE"}}'))
        return _answer("ok")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert llm.complete("x") == "ok"
    assert models == ["gemini-3.8-flash"] * (len(llm.BUSY_WAITS) + 1) + ["gemini-lite"]


def test_503_without_fallback_is_readable(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("MALHAN_GEMINI_FALLBACK", raising=False)
    monkeypatch.setattr("time.sleep", lambda s: None)
    def busy(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b"{}"))
    monkeypatch.setattr(urllib.request, "urlopen", busy)
    with pytest.raises(llm.LlmUnavailable, match="바빠요"):
        llm.complete("x")
