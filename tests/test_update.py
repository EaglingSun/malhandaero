"""켜기 전 자동 업데이트: 임시 저장소 두 개(원격 흉내, 내 폴더)로 받아 오는 흐름을 확인한다."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import update  # noqa: E402

pytestmark = pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, reason="git 없음")


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                          env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
                               "PATH": __import__("os").environ["PATH"], "HOME": str(cwd)}).stdout.strip()


@pytest.fixture
def repos(tmp_path, monkeypatch):
    origin, work, mine = tmp_path / "origin.git", tmp_path / "work", tmp_path / "mine"
    sh(tmp_path, "init", "--bare", "-b", "main", str(origin))
    sh(tmp_path, "clone", "-q", str(origin), str(work))
    (work / "requirements.txt").write_text("fastapi\n")
    (work / "web").mkdir(); (work / "web" / "app.js").write_text("1")
    sh(work, "add", "-A"); sh(work, "commit", "-qm", "1판"); sh(work, "push", "-q", "origin", "main")
    sh(tmp_path, "clone", "-q", str(origin), str(mine))
    monkeypatch.setattr(update, "ROOT", mine)
    fake_venv = mine / ".venv" / "bin" / "python"
    fake_venv.parent.mkdir(parents=True); fake_venv.write_text("")
    monkeypatch.setattr(update, "VENV_PY", fake_venv)
    monkeypatch.delenv("MALHAN_AUTO_UPDATE", raising=False)
    return origin, work, mine


def test_pulls_new_version_and_tells_what_changed(repos, capsys, monkeypatch):
    origin, work, mine = repos
    (work / "web" / "app.js").write_text("2"); sh(work, "commit", "-qam", "화면 고침"); sh(work, "push", "-q", "origin", "main")
    installed = []
    monkeypatch.setattr(update, "install", lambda: installed.append(1))
    assert update.main([]) == 0
    out = capsys.readouterr().out
    assert "새 판을 받았어요" in out and "화면 고침" in out and "새로고침" in out
    assert sh(mine, "rev-parse", "HEAD") == sh(work, "rev-parse", "HEAD")
    assert installed == []                                             # requirements가 그대로면 설치는 안 한다


def test_reinstalls_when_requirements_change_and_warns_about_manifest(repos, capsys, monkeypatch):
    origin, work, mine = repos
    (work / "requirements.txt").write_text("fastapi\nsegno\n"); (work / "web" / "manifest.webmanifest").write_text("{}")
    sh(work, "add", "-A"); sh(work, "commit", "-qm", "2판"); sh(work, "push", "-q", "origin", "main")
    installed = []
    monkeypatch.setattr(update, "install", lambda: installed.append(1))
    assert update.main([]) == 0 and installed == [1]
    assert "다시 추가해 주세요" in capsys.readouterr().out


def test_up_to_date_offline_dirty_and_off_never_block_start(repos, capsys, monkeypatch):
    origin, work, mine = repos
    assert update.main([]) == 0 and "이미 최신 판" in capsys.readouterr().out
    (mine / "requirements.txt").write_text("내가 고침\n")                              # 직접 고친 파일은 덮어쓰지 않는다
    assert update.main([]) == 0 and "덮어쓰지 않고" in capsys.readouterr().out
    sh(mine, "checkout", "-q", "--", "requirements.txt")
    sh(mine, "remote", "set-url", "origin", str(mine / "없는곳"))                      # 인터넷이 끊긴 상황
    assert update.main([]) == 0 and "닿지 못해" in capsys.readouterr().out
    assert update.main(["--no-update"]) == 0 and "꺼져 있어요" in capsys.readouterr().out


def test_plain_folder_gets_adopted_into_the_repo_keeping_data(repos, capsys, monkeypatch, tmp_path):
    origin, work, mine = repos
    plain = tmp_path / "plain"                                                          # 압축을 풀거나 파일만 복사한 폴더
    plain.mkdir(); (plain / "requirements.txt").write_text("fastapi\n"); (plain / "web").mkdir(); (plain / "web" / "app.js").write_text("낡은 판")
    (plain / ".env").write_text("MALHAN_FAMILY_CODE=1234\n"); (plain / "data").mkdir(); (plain / "data" / "malhandaero.db").write_bytes(b"db")
    monkeypatch.setattr(update, "ROOT", plain); monkeypatch.setattr(update, "REPO_URL", str(origin))
    monkeypatch.setattr(update, "VENV_PY", plain / "none"); monkeypatch.setattr(update, "install", lambda: None)
    assert update.main([]) == 0
    out = capsys.readouterr().out
    assert "연결했어요" in out and (plain / ".git").is_dir()
    assert (plain / "web" / "app.js").read_text() == "1"                                # 추적 파일은 저장소 판으로
    assert (plain / ".env").read_text() == "MALHAN_FAMILY_CODE=1234\n" and (plain / "data" / "malhandaero.db").read_bytes() == b"db"
    assert sh(plain, "status", "--porcelain", "--untracked-files=no") == "" and sh(plain, "rev-parse", "--abbrev-ref", "@{u}") == "origin/main"
    assert update.main([]) == 0 and "이미 최신 판" in capsys.readouterr().out             # 두 번째부터는 보통 흐름


def test_adopt_failure_leaves_no_half_repo(capsys, monkeypatch, tmp_path):
    plain = tmp_path / "plain"; plain.mkdir(); (plain / "x.txt").write_text("x")
    monkeypatch.setattr(update, "ROOT", plain); monkeypatch.setattr(update, "REPO_URL", str(tmp_path / "없는곳"))
    monkeypatch.delenv("MALHAN_AUTO_UPDATE", raising=False)
    assert update.main([]) == 0
    assert "연결하지 못했어요" in capsys.readouterr().out and not (plain / ".git").exists() and (plain / "x.txt").read_text() == "x"
