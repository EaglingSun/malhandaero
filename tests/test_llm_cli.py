"""Claude Code 연결 방식: 실제 claude 대신 흉내 실행 파일을 두고 부르는 방식만 확인한다."""
import json
import os
import stat
import sys

import pytest

from server import llm


def fake_claude(tmp_path, body: str):
    exe = tmp_path / "claude"
    exe.write_text(f"#!{sys.executable}\n{body}")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


@pytest.fixture
def cli_mode(monkeypatch):
    monkeypatch.setenv("MALHAN_AI", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    yield


@pytest.mark.skipif(os.name == "nt", reason="흉내 실행 파일이 셔뱅을 쓴다")
def test_claude_cli_gets_prompt_on_stdin_without_api_key(tmp_path, monkeypatch, cli_mode):
    log = tmp_path / "seen.json"
    monkeypatch.setenv("MALHAN_CLAUDE_BIN", fake_claude(tmp_path, f'''
import json, os, sys
json.dump({{"argv": sys.argv[1:], "stdin": sys.stdin.read(), "has_key": "ANTHROPIC_API_KEY" in os.environ, "cwd": os.getcwd()}}, open({str(log)!r}, "w"))
print(json.dumps({{"type": "result", "is_error": False, "result": "[{{\\"text\\": \\"우유 사기\\"}}]"}}))
'''))
    assert llm.mode() == "claude"
    assert llm.complete("녹음 내용: 우유 사야 해") == '[{"text": "우유 사기"}]'
    seen = json.loads(log.read_text())
    assert seen["argv"] == ["-p", "--output-format", "json"] and "우유 사야 해" in seen["stdin"]   # 짧은 글: 모델 지정 없음(Claude Code 기본)
    monkeypatch.setenv("MALHAN_LONG_CHARS", "10")
    llm.complete("녹음 내용: 우유 사야 해 (긴 회의록이라고 치자)")
    assert json.loads(log.read_text())["argv"] == ["-p", "--output-format", "json", "--model", "opus"]   # 긴 글: opus
    monkeypatch.setenv("MALHAN_CLAUDE_MODEL_LONG", ""); monkeypatch.setenv("MALHAN_CLAUDE_MODEL", "sonnet")
    llm.complete("녹음 내용: 우유 사야 해 (긴 회의록이라고 치자)")
    assert json.loads(log.read_text())["argv"][-2:] == ["--model", "sonnet"]
    assert seen["has_key"] is False                      # 구독 로그인을 쓰도록 키는 넘기지 않는다
    assert "malhandaero-repo" not in seen["cwd"]         # 저장소 밖 빈 폴더에서 돈다


@pytest.mark.skipif(os.name == "nt", reason="흉내 실행 파일이 셔뱅을 쓴다")
def test_claude_cli_errors_become_readable(tmp_path, monkeypatch, cli_mode):
    monkeypatch.setenv("MALHAN_CLAUDE_BIN", fake_claude(tmp_path, 'import sys; sys.stderr.write("Not logged in. Please run /login"); sys.exit(1)'))
    with pytest.raises(llm.LlmUnavailable, match="로그인"):
        llm.complete("x")
    monkeypatch.setenv("MALHAN_CLAUDE_BIN", fake_claude(tmp_path, 'import json; print(json.dumps({"is_error": True, "result": "usage limit reached"}))'))
    with pytest.raises(llm.LlmUnavailable, match="usage limit"):
        llm.complete("x")


@pytest.mark.skipif(os.name == "nt", reason="흉내 실행 파일이 셔뱅을 쓴다")
def test_claude_cli_reads_photo_from_its_folder(tmp_path, monkeypatch, cli_mode):
    from PIL import Image

    img = tmp_path / "big.png"
    Image.new("RGB", (4000, 3000), "white").save(img)
    monkeypatch.setenv("MALHAN_CLAUDE_BIN", fake_claude(tmp_path, '''
import json, os, sys
ok = os.path.exists("photo.jpg") and "--allowedTools" in sys.argv and "photo.jpg" in sys.stdin.read()
print(json.dumps({"is_error": False, "result": "영수증: 두부 1" if ok else "사진 없음"}))
'''))
    assert llm.read_image(img) == "영수증: 두부 1"


def test_mode_prefers_explicit_setting(monkeypatch):
    monkeypatch.delenv("MALHAN_FAKE_LLM", raising=False)
    monkeypatch.setenv("MALHAN_AI", "api")
    assert llm.mode() == "anthropic"
    monkeypatch.setenv("MALHAN_AI", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert llm.mode() == "anthropic"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("MALHAN_CLAUDE_BIN", "/somewhere/claude")
    assert llm.mode() == "claude"
