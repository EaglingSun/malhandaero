"""Codex CLI 방식과 gpt 프리셋, AI 없음 모드."""
import os
import stat
import sys

import pytest

from server import llm


def _fake_codex(tmp_path, body):
    exe = tmp_path / ("codex.cmd" if os.name == "nt" else "codex")
    exe.write_text(body, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="sh 가짜 실행 파일")
def test_codex_exec_reads_stdin_and_writes_output_file(tmp_path, monkeypatch):
    exe = _fake_codex(tmp_path, """#!/bin/sh
# -o 뒤의 파일에 답을 쓰고, 표준 입력(지시문)을 그대로 돌려준다
out=""; while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; esac; shift; done
p=$(cat); printf '[{"text": "%s"}]' "$p" > "$out"
""")
    monkeypatch.setenv("MALHAN_AI", "codex"); monkeypatch.setenv("MALHAN_CODEX_BIN", exe)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm.mode() == "codex"
    assert llm.complete("우유 사기") == '[{"text": "우유 사기"}]'


@pytest.mark.skipif(sys.platform.startswith("win"), reason="sh 가짜 실행 파일")
def test_codex_not_logged_in(tmp_path, monkeypatch):
    exe = _fake_codex(tmp_path, "#!/bin/sh\necho 'error: not logged in, run codex login' >&2; exit 1\n")
    monkeypatch.setenv("MALHAN_AI", "codex"); monkeypatch.setenv("MALHAN_CODEX_BIN", exe)
    with pytest.raises(llm.LlmUnavailable, match="codex login"):
        llm.complete("x")


def test_autodetect_order(monkeypatch):
    for k in ("MALHAN_AI", "MALHAN_FAKE_LLM", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm, "_claude_bin", lambda: None); monkeypatch.setattr(llm, "_codex_bin", lambda: None)
    assert llm.mode() == "none"
    monkeypatch.setenv("GEMINI_API_KEY", "g"); assert llm.mode() == "gemini"
    monkeypatch.setenv("OPENAI_API_KEY", "o"); assert llm.mode() == "gpt"
    monkeypatch.setattr(llm, "_codex_bin", lambda: "/usr/bin/codex"); assert llm.mode() == "codex"
    monkeypatch.setattr(llm, "_claude_bin", lambda: "/usr/bin/claude"); assert llm.mode() == "claude"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a"); assert llm.mode() == "anthropic"


def test_gpt_preset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x"); monkeypatch.delenv("MALHAN_OPENAI_BASE_URL", raising=False); monkeypatch.delenv("MALHAN_OPENAI_MODEL", raising=False)
    base, key, model, name = llm.openai_config("gpt")
    assert base == "https://api.openai.com/v1" and key == "sk-x" and model == "gpt-5.4-mini" and name == "OpenAI"


def test_no_ai_mode_keeps_manual_items_and_calendar_message(monkeypatch):
    for k in ("MALHAN_AI", "MALHAN_FAKE_LLM", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm, "_claude_bin", lambda: None); monkeypatch.setattr(llm, "_codex_bin", lambda: None)
    with pytest.raises(llm.LlmUnavailable, match="직접 적기와 캘린더는"):
        llm.complete("x")
