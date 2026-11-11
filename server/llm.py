"""AI 호출을 한 곳에 모은다. 다른 모델로 바꿀 때 이 파일만 고친다.

연결 방식 (MALHAN_AI로 고정하거나, 비워 두면 위에서부터 되는 것을 고른다)
  api    : ANTHROPIC_API_KEY가 있으면 Anthropic API (쓴 만큼 과금)
  claude : 이 PC에 설치·로그인된 Claude Code를 `claude -p`로 부른다 (본인 구독 사용, API 결제 없음)
  codex  : 이 PC에 설치·로그인된 OpenAI Codex CLI를 `codex exec`로 부른다 (ChatGPT 구독 사용)
  gpt    : OpenAI API (OPENAI_API_KEY, 쓴 만큼 과금). 기본 모델 gpt-5.4-mini
  gemini : 구글 Gemini API (무료 티어 있음). GEMINI_API_KEY 필요
  ollama : 이 PC의 Ollama (완전 무료·오프라인, 작은 모델은 회의록 품질이 떨어짐)
  openai : 그 밖의 OpenAI 호환 서버 (MALHAN_OPENAI_BASE_URL · MALHAN_OPENAI_API_KEY · MALHAN_OPENAI_MODEL)
  fake   : 키도 로그인도 없이 화면만 확인하는 규칙 기반 흉내 (정확도 낮음)

그 밖의 환경 변수
  MALHAN_MODEL              : api 방식의 모델 이름 (기본 claude-sonnet-5-5)
  MALHAN_CLAUDE_MODEL       : claude 방식에서 짧은 글에 쓸 모델. 비우면 Claude Code의 기본 모델 (기본: 비움)
  MALHAN_CLAUDE_MODEL_LONG  : claude 방식에서 긴 글(회의록 등)에 쓸 모델 (기본 opus). 비우면 짧은 글과 같게
  MALHAN_LONG_CHARS         : 이 글자 수를 넘는 지시문이면 '긴 글'로 본다 (기본 10000)
  MALHAN_CLAUDE_BIN         : claude 실행 파일 위치 (기본: PATH에서 찾음)
  MALHAN_FAKE_LLM=1         : MALHAN_AI=fake와 같다
  MALHAN_CODEX_BIN / MALHAN_CODEX_MODEL : codex 실행 파일 위치 / 모델 (비우면 Codex 기본)
  MALHAN_GPT_MODEL          : gpt 방식의 모델 (기본 gpt-5.4-mini)
  MALHAN_GEMINI_MODEL       : gemini 방식의 모델 (기본 gemini-3.8-flash). 구글이 "다른 모델을 쓰라"고 답하면 그 모델로 한 번 더 시도한다
  MALHAN_OLLAMA_MODEL       : ollama 방식의 모델 (기본 qwen3:8b), MALHAN_OLLAMA_URL (기본 http://localhost:11434)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CLI_TIMEOUT = int(os.environ.get("MALHAN_CLI_TIMEOUT", "1800"))  # 초. Claude Code는 부를 때마다 새로 떠서 API보다 느리고, 긴 회의록(opus)은 5~10분도 걸린다
HTTP_TIMEOUT = int(os.environ.get("MALHAN_HTTP_TIMEOUT", "600"))  # 초. Gemini 등 바깥 API. 긴 회의록은 1~3분 걸릴 수 있다


class LlmUnavailable(RuntimeError):
    pass


def _claude_bin() -> str | None:
    return os.environ.get("MALHAN_CLAUDE_BIN") or shutil.which("claude")


OPENAI_LIKE = ("openai", "gpt", "gemini", "ollama")
CLI_MODES = ("claude", "codex")


def _codex_bin() -> str | None:
    return os.environ.get("MALHAN_CODEX_BIN") or shutil.which("codex")


def mode() -> str:
    """자동 감지 순서: Anthropic 키 → Claude Code → Codex → OpenAI 키 → Gemini 키. MALHAN_AI로 고정 가능."""
    forced = os.environ.get("MALHAN_AI", "").strip().lower()
    if forced in ("api", "fake") + CLI_MODES + OPENAI_LIKE:
        return {"api": "anthropic"}.get(forced, forced)
    if os.environ.get("MALHAN_FAKE_LLM") == "1":
        return "fake"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _claude_bin():
        return "claude"
    if _codex_bin():
        return "codex"
    if os.environ.get("OPENAI_API_KEY"):
        return "gpt"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    return "none"


NO_AI = ("AI가 연결되지 않았어요. 직접 적기와 캘린더는 그대로 쓸 수 있어요. 녹음·글에서 뽑으려면 이 PC에 Claude Code나 Codex를 로그인하거나, "
         ".env에 ANTHROPIC_API_KEY · OPENAI_API_KEY · GEMINI_API_KEY 중 하나를 넣어 주세요.")


def _run_codex(prompt: str, image: Path | None = None) -> str:
    """이 PC의 Codex CLI를 한 번 불러 답을 받는다(codex exec, 읽기 전용 샌드박스). 본인 ChatGPT 로그인을 쓴다."""
    exe = _codex_bin()
    if not exe:
        raise LlmUnavailable(NO_AI)
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "CODEX_API_KEY")}
    with tempfile.TemporaryDirectory(prefix="malhan-cx-") as tmp:
        out = Path(tmp) / "answer.txt"
        cmd = [exe, "exec", "-s", "read-only", "--skip-git-repo-check", "-o", str(out)]
        model = os.environ.get("MALHAN_CODEX_MODEL", "").strip()
        if model:
            cmd += ["-m", model]
        if image:
            cmd += ["-i", str(image)]
        cmd.append("-")  # 지시문은 표준 입력으로
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp, timeout=CLI_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise LlmUnavailable("Codex가 제때 답하지 않았어요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")
        except OSError:
            raise LlmUnavailable("Codex를 실행하지 못했어요. 설치와 PATH를 확인해 주세요.")
        text = out.read_text(encoding="utf-8").strip() if out.exists() else (r.stdout or "").strip()
    if r.returncode == 0 and text:
        return text
    detail = (r.stderr or r.stdout or "")[-200:]
    if any(w in detail.lower() for w in ("login", "logged", "auth", "unauthorized")):
        raise LlmUnavailable("Codex에 로그인되어 있지 않아요. 이 PC의 터미널에서 'codex login'을 해 주세요.")
    raise LlmUnavailable("Codex가 답을 주지 못했어요: " + detail.strip()[:160])


def openai_config(m: str) -> tuple[str, str, str, str]:
    """OpenAI 호환 방식의 (base_url, api_key, model, 이름). gpt/gemini/ollama는 기본값을 채워 둔다."""
    if m == "gpt":
        return (os.environ.get("MALHAN_OPENAI_BASE_URL") or "https://api.openai.com/v1",
                os.environ.get("OPENAI_API_KEY") or os.environ.get("MALHAN_OPENAI_API_KEY", ""),
                os.environ.get("MALHAN_GPT_MODEL") or os.environ.get("MALHAN_OPENAI_MODEL") or "gpt-5.4-mini", "OpenAI")
    if m == "gemini":
        return (os.environ.get("MALHAN_OPENAI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai",
                os.environ.get("GEMINI_API_KEY") or os.environ.get("MALHAN_OPENAI_API_KEY", ""),
                os.environ.get("MALHAN_GEMINI_MODEL") or os.environ.get("MALHAN_OPENAI_MODEL") or "gemini-3.8-flash", "Gemini")
    if m == "ollama":
        return ((os.environ.get("MALHAN_OLLAMA_URL") or "http://localhost:11434").rstrip("/") + "/v1", "ollama",
                os.environ.get("MALHAN_OLLAMA_MODEL") or os.environ.get("MALHAN_OPENAI_MODEL") or "qwen3:8b", "Ollama")
    return (os.environ.get("MALHAN_OPENAI_BASE_URL", "").rstrip("/"), os.environ.get("MALHAN_OPENAI_API_KEY", ""),
            os.environ.get("MALHAN_OPENAI_MODEL", ""), "AI 서버")


_SUGGESTED = re.compile(r"use\s+(?:models/)?([\w.\-]+)")


def suggested_model(detail: str) -> str:
    """'This model X is no longer available… use models/Y' 꼴의 답에서 Y를 꺼낸다."""
    m = _SUGGESTED.search(detail or "")
    return m.group(1) if m else ""


BUSY_WAITS = (5, 15, 40)  # 503(수요 폭주)·429(한도)에 기다렸다 다시 시도하는 간격(초)


def _busy_retry(name: str, model: str, code: int, attempt: int) -> bool:
    """잠깐 기다리면 풀리는 오류면 기다리고 True. 더 못 기다리면 False."""
    import time

    if attempt >= len(BUSY_WAITS):
        return False
    wait = BUSY_WAITS[attempt]
    print(f"[llm] {name} {model} → {code}, {wait}초 뒤 다시 ({attempt + 1}/{len(BUSY_WAITS)})", flush=True)
    time.sleep(wait)
    return True


def gemini_alternatives(key: str, current: str) -> list[str]:
    """이 키로 쓸 수 있는 다른 flash 계열 모델. lite·이전 판 순으로(덜 붐비는 쪽부터)."""
    import urllib.request

    try:
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=200")
        with urllib.request.urlopen(req, timeout=20) as r:
            models = json.loads(r.read().decode("utf-8")).get("models", [])
    except Exception:
        return []
    names = [mm.get("name", "").removeprefix("models/") for mm in models
             if "generateContent" in mm.get("supportedGenerationMethods", [])]
    cands = [n for n in names if "flash" in n and n != current and not any(x in n for x in ("image", "tts", "audio", "live", "preview", "exp", "embedding"))]
    def rank(n: str):
        return (0 if "lite" in n else 1, -float("".join(c for c in n.split("-")[1] if c.isdigit() or c == ".") or 0) if "-" in n else 0)
    try:
        cands.sort(key=rank)
    except Exception:
        pass
    return cands[:3]


def _run_openai(m: str, content, max_tokens: int, model_override: str = "", plain: bool = False, attempt: int = 0) -> str:
    """OpenAI 호환 chat/completions 한 번. 표준 라이브러리만 쓴다(설치 없음).
    Gemini는 '생각' 수준을 낮춰(reasoning_effort) 빨리 답하게 한다. 그 옵션을 거부하면 빼고 한 번 더.
    503(수요 폭주)·429(한도)는 몇 번 기다렸다 다시, 그래도 안 되면 MALHAN_GEMINI_FALLBACK 모델로 한 번 더."""
    import time
    import urllib.error
    import urllib.request

    base, key, model, name = openai_config(m)
    model = model_override or model
    if not base or not model:
        raise LlmUnavailable(f"{name} 주소나 모델이 비어 있어요. .env의 MALHAN_OPENAI_BASE_URL · MALHAN_OPENAI_MODEL을 채워 주세요.")
    if m == "gemini" and not key:
        raise LlmUnavailable("Gemini 키가 없어요. .env에 GEMINI_API_KEY를 넣어 주세요 (aistudio.google.com에서 무료 발급).")
    if m == "gpt" and not key:
        raise LlmUnavailable("OpenAI 키가 없어요. .env에 OPENAI_API_KEY를 넣어 주세요.")
    payload = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}
    if m != "gpt":
        payload["temperature"] = 0.2  # gpt-5 계열은 temperature를 거부한다
    if m in ("gemini", "gpt") and not plain:
        payload["reasoning_effort"] = os.environ.get("MALHAN_GEMINI_EFFORT", "low")
    body = json.dumps(payload).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key or 'none'}"})
    size = len(content) if isinstance(content, str) else sum(len(p.get("text", "")) for p in content)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
        print(f"[llm] {name} {model} {size}자 → {time.time() - t0:.0f}초", flush=True)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        print(f"[llm] {name} {model} {size}자 → HTTP {e.code} ({time.time() - t0:.0f}초): {detail[:120]}", flush=True)
        if e.code == 400 and "reasoning" in detail and not plain:
            return _run_openai(m, content, max_tokens, model_override, plain=True, attempt=attempt)
        if e.code in (401, 403):
            raise LlmUnavailable(f"{name} 키가 틀리거나 권한이 없어요.")
        if e.code in (503, 429):
            if _busy_retry(name, model, e.code, attempt):
                return _run_openai(m, content, max_tokens, model_override, plain, attempt + 1)
            fallback = os.environ.get("MALHAN_GEMINI_FALLBACK", "").strip() if m == "gemini" else ""
            tried = set(os.environ.get("_MALHAN_TRIED", "").split(",")) | {model}
            if m == "gemini" and not fallback:
                alts = [a for a in gemini_alternatives(key, model) if a not in tried]
                fallback = alts[0] if alts else ""
            if fallback and fallback not in tried:
                print(f"[llm] {name} {model}이 계속 바빠요. 대신 {fallback}로 시도", flush=True)
                os.environ["_MALHAN_TRIED"] = ",".join(tried | {fallback})
                try:
                    return _run_openai(m, content, max_tokens, fallback, plain, attempt=len(BUSY_WAITS) - 1)
                finally:
                    os.environ.pop("_MALHAN_TRIED", None)
            if e.code == 429:
                raise LlmUnavailable(f"{name} 사용량 한도예요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")
            raise LlmUnavailable(f"{name}가 지금 너무 바빠요(503). 몇 분 뒤 '다시 뽑기'를 눌러 주세요.")
        if e.code == 404 and m == "ollama":
            raise LlmUnavailable(f"Ollama에 '{model}' 모델이 없어요. 터미널에서 'ollama pull {model}'을 해 주세요.")
        if e.code == 404 and not model_override and suggested_model(detail):
            new = suggested_model(detail)
            print(f"[llm] {name} 모델 '{model}'은 더 못 써요. 구글이 권한 '{new}'로 다시 시도합니다. .env의 MALHAN_GEMINI_MODEL을 바꿔 두세요.", flush=True)
            return _run_openai(m, content, max_tokens, model_override=new)
        if e.code == 404:
            raise LlmUnavailable(f"{name}에 '{model}' 모델이 없어요. .env의 모델 이름을 확인해 주세요.")
        raise LlmUnavailable(f"{name}가 답을 주지 못했어요 ({e.code}): {detail}")
    except urllib.error.URLError as e:
        print(f"[llm] {name} {model} → 연결 실패 ({time.time() - t0:.0f}초): {e.reason}", flush=True)
        if m == "ollama":
            raise LlmUnavailable("Ollama가 켜져 있지 않아요. 'ollama serve'를 실행해 주세요.")
        if "timed out" in str(e.reason):
            raise LlmUnavailable(f"{name}가 {HTTP_TIMEOUT // 60}분 안에 답하지 않았어요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")
        raise LlmUnavailable(f"{name}에 연결하지 못했어요: {e.reason}")
    except TimeoutError:
        print(f"[llm] {name} {model} {size}자 → {HTTP_TIMEOUT}초 안에 답 없음", flush=True)
        raise LlmUnavailable(f"{name}가 {HTTP_TIMEOUT // 60}분 안에 답하지 않았어요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise LlmUnavailable(f"{name} 응답 형식을 읽지 못했어요.")
    # 생각 과정을 함께 내놓는 모델(qwen3 등)의 <think>…</think>는 걷어낸다
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def claude_model_for(prompt: str) -> str:
    """긴 글(회의록)은 더 센 모델로. 비어 있으면 Claude Code 기본 모델을 쓴다."""
    long_ = len(prompt) > int(os.environ.get("MALHAN_LONG_CHARS", "10000"))
    model = os.environ.get("MALHAN_CLAUDE_MODEL_LONG", "opus") if long_ else os.environ.get("MALHAN_CLAUDE_MODEL", "")
    return (model or os.environ.get("MALHAN_CLAUDE_MODEL", "")).strip()


def _run_claude(prompt: str, workdir: Path | None = None, allow_read: bool = False) -> str:
    """이 PC의 Claude Code를 한 번 불러 답을 받는다. 본인 로그인(구독)을 쓰도록 API 키는 넘기지 않는다."""
    exe = _claude_bin()
    if not exe:
        raise LlmUnavailable(NO_AI)
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    cmd = [exe, "-p", "--output-format", "json"]
    model = claude_model_for(prompt)
    if model:
        cmd += ["--model", model]
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
    if m == "codex":
        return _run_codex(prompt)
    if m in OPENAI_LIKE:
        return _run_openai(m, prompt, max_tokens)
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
    if m == "codex":
        with tempfile.TemporaryDirectory(prefix="malhan-img-") as tmp:
            img = Path(tmp) / "photo.jpg"
            img.write_bytes(data)
            return _run_codex(READ_IMAGE_PROMPT, image=img).strip()
    if m in OPENAI_LIKE:
        import base64

        url = f"data:{media_type};base64," + base64.b64encode(data).decode()
        return _run_openai(m, [{"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": READ_IMAGE_PROMPT}], 2000)
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
