"""AI 호출을 한 곳에 모은다. 다른 모델로 바꿀 때 이 파일만 고친다.

연결 방식 (MALHAN_AI로 고정하거나, 비워 두면 위에서부터 되는 것을 고른다)
  api    : ANTHROPIC_API_KEY가 있으면 Anthropic API (쓴 만큼 과금)
  claude : 이 PC에 설치·로그인된 Claude Code를 `claude -p`로 부른다 (본인 구독 사용, API 결제 없음)
  fake   : 키도 로그인도 없이 화면만 확인하는 규칙 기반 흉내 (정확도 낮음)

그 밖의 환경 변수
  MALHAN_MODEL       : api 방식의 모델 이름 (기본 claude-sonnet-5-5)
  MALHAN_CLAUDE_BIN  : claude 실행 파일 위치 (기본: PATH에서 찾음)
  MALHAN_FAKE_LLM=1  : MALHAN_AI=fake와 같다
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CLI_TIMEOUT = 240  # 초. Claude Code는 부를 때마다 새로 떠서 API보다 느리다


class LlmUnavailable(RuntimeError):
    pass


def _claude_bin() -> str | None:
    return os.environ.get("MALHAN_CLAUDE_BIN") or shutil.which("claude")


def mode() -> str:
    forced = os.environ.get("MALHAN_AI", "").strip().lower()
    if forced in ("api", "claude", "fake"):
        return {"api": "anthropic"}.get(forced, forced)
    if os.environ.get("MALHAN_FAKE_LLM") == "1":
        return "fake"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _claude_bin():
        return "claude"
    return "none"


NO_AI = "AI가 연결되지 않았어요. 이 PC에 Claude Code를 설치해 로그인하거나, .env에 ANTHROPIC_API_KEY를 넣어 주세요."


def _run_claude(prompt: str, workdir: Path | None = None, allow_read: bool = False) -> str:
    """이 PC의 Claude Code를 한 번 불러 답을 받는다. 본인 로그인(구독)을 쓰도록 API 키는 넘기지 않는다."""
    exe = _claude_bin()
    if not exe:
        raise LlmUnavailable(NO_AI)
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    cmd = [exe, "-p", "--output-format", "json"]
    if allow_read:
        cmd += ["--allowedTools", "Read"]
    with tempfile.TemporaryDirectory(prefix="malhan-cc-") as tmp:
        # 빈 폴더에서 돌린다: 이 저장소의 설정이나 지침이 끼어들지 않게
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               env=env, cwd=str(workdir or tmp), timeout=CLI_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise LlmUnavailable("Claude Code가 제때 답하지 않았어요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")
        except OSError:
            raise LlmUnavailable("Claude Code를 실행하지 못했어요. 설치와 PATH를 확인해 주세요.")
    out = (r.stdout or "").strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and not data.get("is_error") and isinstance(data.get("result"), str):
        return data["result"]
    detail = (data.get("result") if isinstance(data, dict) else "") or (r.stderr or out)[-200:]
    if "login" in str(detail).lower() or "logged" in str(detail).lower() or "auth" in str(detail).lower():
        raise LlmUnavailable("Claude Code에 로그인되어 있지 않아요. 이 PC의 터미널에서 'claude'를 실행해 로그인해 주세요.")
    raise LlmUnavailable("Claude Code가 답을 주지 못했어요: " + str(detail).strip()[:160])


def complete(prompt: str, max_tokens: int = 2000) -> str:
    m = mode()
    if m == "fake":
        return _fake(prompt)
    if m == "claude":
        return _run_claude(prompt)
    if m == "none":
        raise LlmUnavailable(NO_AI)
    import anthropic  # 늦은 가져오기: 키 없이 시험할 때 필요 없게

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("MALHAN_MODEL", "claude-sonnet-5-5"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


_TODO_HINT = re.compile(r"(할게|하겠|해야|챙겨|보낼게|보내겠|드릴게|드리겠|사야|써야|예약해|전화해|잊지)")


def _fake(prompt: str) -> str:
    """키 없이 흐름만 확인하는 용도. 문장에 다짐 표현이 있으면 그대로 항목으로 만든다."""
    if "<<<" not in prompt:
        return "오늘 기록을 정리했어요. 남은 일은 내일로 넘어가요."
    body = prompt.split("<<<", 1)[1].rsplit(">>>", 1)[0]
    out = []
    for sent in re.split(r"(?<=[.?!。])\s+|\n+", body):
        s = re.sub(r"^\s*\[?[^\]:：]{1,12}\]?\s*[:：]\s*", "", sent).strip()
        if s and _TODO_HINT.search(s):
            out.append({"text": s[:60], "due": "", "dueDate": None, "scope": "개인", "quote": s})
    return json.dumps(out, ensure_ascii=False)


READ_IMAGE_PROMPT = (
    "이 사진에 보이는 내용을 글로 옮겨 적어라. 안내문·메모·칠판·화면 캡처면 적힌 글을 그대로, "
    "영수증이면 가게 이름, 날짜, 품목과 수량을 한 줄에 하나씩 적는다. "
    "글이 없는 사진이면 무엇이 찍혔는지 한두 문장으로 적는다. 보이지 않는 내용을 추측해서 보태지 않는다. "
    "설명이나 머리말 없이 옮겨 적은 내용만 출력한다."
)


def _image_bytes(path) -> tuple[bytes, str]:
    """큰 사진은 줄여서 보낸다. Pillow가 없으면 원본 그대로(4MB 이하만)."""
    import io
    from pathlib import Path

    path = Path(path)
    try:
        from PIL import Image, ImageOps

        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        img.thumbnail((1568, 1568))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        raw = path.read_bytes()
        if len(raw) > 4 * 1024 * 1024:
            raise LlmUnavailable("사진이 커서 읽지 못했어요. 서버에 'pip install pillow'를 해 주세요.")
        ext = path.suffix.lower().lstrip(".")
        return raw, {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
    except Exception:
        raise LlmUnavailable("이 사진 형식은 읽지 못했어요. JPG나 PNG로 넣어 주세요.")


def read_image(path) -> str:
    """사진 → 글. 녹음을 글로 바꾸는 것과 같은 자리의 단계다."""
    m = mode()
    data, media_type = _image_bytes(path)
    if m == "fake":
        return "우유 사야 해. 금요일까지 가정통신문 회신 챙겨야 해."
    if m == "claude":
        # 줄인 사진을 임시 폴더에 두고, Claude Code가 그 파일을 열어 읽게 한다
        with tempfile.TemporaryDirectory(prefix="malhan-img-") as tmp:
            (Path(tmp) / "photo.jpg").write_bytes(data)
            return _run_claude("이 폴더의 photo.jpg 파일을 Read 도구로 열어 본 뒤 답하라.\n\n" + READ_IMAGE_PROMPT,
                               workdir=Path(tmp), allow_read=True).strip()
    if m == "none":
        raise LlmUnavailable(NO_AI)
    import base64

    import anthropic

    msg = anthropic.Anthropic().messages.create(
        model=os.environ.get("MALHAN_MODEL", "claude-sonnet-5-5"),
        max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()}},
            {"type": "text", "text": READ_IMAGE_PROMPT},
        ]}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
