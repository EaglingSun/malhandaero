"""Gemini가 녹음을 직접 듣는 경로: 엔진 선택, 작은 파일은 inline, 큰 파일은 File API."""
import io
import json
import urllib.request

import pytest

from server import stt


class Resp(io.BytesIO):
    def __init__(self, payload, headers=None):
        super().__init__(json.dumps(payload).encode()); self.headers = headers or {}
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_engine_selection(monkeypatch):
    monkeypatch.delenv("MALHAN_STT", raising=False); monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(stt, "_whisper_available", lambda: False)
    assert stt.engine() == "none" and not stt.available()
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert stt.engine() == "gemini" and stt.available()
    monkeypatch.setattr(stt, "_whisper_available", lambda: True)
    assert stt.engine() == "whisper"                       # 둘 다 있으면 로컬 우선
    monkeypatch.setenv("MALHAN_STT", "gemini")
    assert stt.engine() == "gemini"


def test_small_file_goes_inline(monkeypatch, tmp_path):
    monkeypatch.setenv("MALHAN_STT", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k")
    f = tmp_path / "통화.m4a"; f.write_bytes(b"\x00" * 100)
    seen = {}
    def fake(req, timeout=0):
        seen["url"] = req.full_url; seen["body"] = json.loads(req.data)
        return Resp({"candidates": [{"content": {"parts": [{"text": "화자1: 우유 사 갈게.\n화자2: 응."}]}}]})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert stt.transcribe(f) == "화자1: 우유 사 갈게.\n화자2: 응."
    assert "gemini-3.8-flash:generateContent" in seen["url"] and "key=k" in seen["url"]
    part = seen["body"]["contents"][0]["parts"][0]["inline_data"]
    assert part["mime_type"] == "audio/mp4" and len(part["data"]) > 0


def test_big_file_uses_file_api(monkeypatch, tmp_path):
    monkeypatch.setenv("MALHAN_STT", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(stt, "GEMINI_INLINE_MAX", 10)
    f = tmp_path / "회의.mp3"; f.write_bytes(b"\x00" * 50)
    calls = []
    def fake(req, timeout=0):
        calls.append((req.get_method(), req.full_url, dict(req.headers)))
        if "/upload/" in req.full_url:
            return Resp({}, {"X-Goog-Upload-URL": "https://up.example/session"})
        if req.full_url.startswith("https://up.example/"):
            return Resp({"file": {"name": "files/abc", "uri": "https://generativelanguage.googleapis.com/v1beta/files/abc", "state": "PROCESSING"}})
        if "/files/abc" in req.full_url:
            return Resp({"name": "files/abc", "uri": "https://generativelanguage.googleapis.com/v1beta/files/abc", "state": "ACTIVE"})
        body = json.loads(req.data)
        assert body["contents"][0]["parts"][0]["file_data"]["file_uri"].endswith("/files/abc")
        return Resp({"candidates": [{"content": {"parts": [{"text": "받아 적은 글"}]}}]})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert stt.transcribe(f) == "받아 적은 글"
    assert [c[0] for c in calls] == ["POST", "POST", "GET", "POST"]
    assert calls[1][2].get("X-goog-upload-command") == "upload, finalize"


def test_gemini_auth_error_is_readable(monkeypatch, tmp_path):
    import urllib.error
    monkeypatch.setenv("MALHAN_STT", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "bad")
    f = tmp_path / "a.wav"; f.write_bytes(b"x")
    def denied(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 403, "forbidden", {}, io.BytesIO(b"{}"))
    monkeypatch.setattr(urllib.request, "urlopen", denied)
    with pytest.raises(stt.SttUnavailable, match="GEMINI_API_KEY"):
        stt.transcribe(f)
