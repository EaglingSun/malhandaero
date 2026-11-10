"""음성 → 글. 집 PC에서 로컬로 돌린다(faster-whisper). 다른 엔진으로 바꿀 때 이 파일만 고친다.

환경 변수
  MALHAN_STT           : whisper | gemini (비우면: faster-whisper가 있으면 whisper, 없는데 Gemini 키가 있으면 gemini)
  MALHAN_WHISPER_MODEL : tiny | base | small | medium | large-v3 (기본 small)
  MALHAN_WHISPER_DEVICE: cpu | cuda (기본 cpu)
  Gemini 방식은 녹음 파일을 Gemini가 직접 듣는다(설치 없음, 화자 구분 시도). 18MB 넘는 파일은 File API로 올린 뒤 쓴다.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class SttUnavailable(RuntimeError):
    pass


def _whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def _gemini_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "") or (os.environ.get("MALHAN_OPENAI_API_KEY", "") if os.environ.get("MALHAN_AI", "").lower() == "gemini" else "")


def engine() -> str:
    """whisper | gemini | none"""
    forced = os.environ.get("MALHAN_STT", "").strip().lower()
    if forced in ("whisper", "gemini"):
        return forced
    if _whisper_available():
        return "whisper"
    if _gemini_key():
        return "gemini"
    return "none"


def available() -> bool:
    return engine() != "none"


GEMINI_BASE = "https://generativelanguage.googleapis.com"
GEMINI_INLINE_MAX = 18 * 1024 * 1024
TRANSCRIBE_PROMPT = (
    "이 녹음을 한국어로 받아 적어라. 들리는 말을 그대로, 빠짐없이 적는다. 요약하거나 고치지 않는다. "
    "말하는 사람이 둘 이상이고 구분이 되면 줄 앞에 '화자1:', '화자2:'처럼 붙이고, 구분이 안 되면 붙이지 않는다. "
    "시간 표시·머리말·설명 없이 받아 적은 글만 출력한다."
)
MIME = {".m4a": "audio/mp4", ".mp4": "audio/mp4", ".aac": "audio/aac", ".mp3": "audio/mpeg", ".wav": "audio/wav",
        ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac", ".amr": "audio/amr", ".3gp": "audio/3gpp"}


def _gemini_call(url: str, body: bytes | None, headers: dict, method: str = "POST", timeout: int = 600):
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return (json.loads(raw.decode("utf-8")) if raw.strip() else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code in (401, 403):
            raise SttUnavailable("Gemini 키가 틀리거나 권한이 없어요. .env의 GEMINI_API_KEY를 확인해 주세요.")
        if e.code == 429:
            raise SttUnavailable("Gemini 사용량 한도예요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")
        raise SttUnavailable(f"Gemini가 녹음을 읽지 못했어요 ({e.code}): {detail}")
    except urllib.error.URLError as e:
        raise SttUnavailable(f"Gemini에 연결하지 못했어요: {e.reason}")
    except TimeoutError:
        raise SttUnavailable("Gemini가 제때 답하지 않았어요. 잠시 뒤 '다시 뽑기'를 눌러 주세요.")


def _gemini_upload(path: Path, mime: str, key: str) -> str:
    """File API(resumable)로 올리고 처리가 끝날 때까지 기다린 뒤 file_uri를 돌려준다."""
    import json
    import time

    data = path.read_bytes()
    start = {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
             "X-Goog-Upload-Header-Content-Length": str(len(data)), "X-Goog-Upload-Header-Content-Type": mime,
             "Content-Type": "application/json"}
    _, hdr = _gemini_call(f"{GEMINI_BASE}/upload/v1beta/files?key={key}", json.dumps({"file": {"display_name": path.name}}).encode(), start, timeout=60)
    upload_url = next((v for k, v in hdr.items() if k.lower() == "x-goog-upload-url"), "")
    if not upload_url:
        raise SttUnavailable("Gemini 파일 올리기를 시작하지 못했어요.")
    info, _ = _gemini_call(upload_url, data, {"X-Goog-Upload-Command": "upload, finalize", "X-Goog-Upload-Offset": "0", "Content-Type": mime}, timeout=900)
    f = info.get("file", {})
    name, uri = f.get("name", ""), f.get("uri", "")
    for _ in range(120):  # 처리 대기 (최대 ~4분)
        if f.get("state") != "PROCESSING":
            break
        time.sleep(2)
        f, _ = _gemini_call(f"{GEMINI_BASE}/v1beta/{name}?key={key}", None, {}, method="GET", timeout=30)
    if f.get("state") == "FAILED" or not uri:
        raise SttUnavailable("Gemini가 이 녹음 파일을 처리하지 못했어요. m4a·mp3·wav인지 확인해 주세요.")
    return uri


def _transcribe_gemini(path: Path) -> str:
    import base64
    import json

    key = _gemini_key()
    if not key:
        raise SttUnavailable("Gemini 키가 없어요. .env에 GEMINI_API_KEY를 넣어 주세요.")
    model = os.environ.get("MALHAN_GEMINI_STT_MODEL") or os.environ.get("MALHAN_GEMINI_MODEL") or "gemini-2.5-flash"
    mime = MIME.get(path.suffix.lower(), "audio/mp4")
    if path.stat().st_size <= GEMINI_INLINE_MAX:
        part = {"inline_data": {"mime_type": mime, "data": base64.b64encode(path.read_bytes()).decode()}}
    else:
        part = {"file_data": {"mime_type": mime, "file_uri": _gemini_upload(path, mime, key)}}
    body = {"contents": [{"parts": [part, {"text": TRANSCRIBE_PROMPT}]}], "generationConfig": {"temperature": 0.1}}
    data, _ = _gemini_call(f"{GEMINI_BASE}/v1beta/models/{model}:generateContent?key={key}", json.dumps(body).encode(),
                           {"Content-Type": "application/json"})
    try:
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError):
        raise SttUnavailable("Gemini 응답에서 글을 찾지 못했어요. 녹음이 너무 짧거나 비어 있는지 확인해 주세요.")
    return text.strip()


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    device = os.environ.get("MALHAN_WHISPER_DEVICE", "cpu")
    return WhisperModel(
        os.environ.get("MALHAN_WHISPER_MODEL", "small"),
        device=device,
        compute_type="int8" if device == "cpu" else "float16",
    )


def transcribe(path: Path) -> str:
    eng = engine()
    if eng == "gemini":
        return _transcribe_gemini(Path(path))
    if eng == "none":
        raise SttUnavailable(
            "이 PC에 음성 인식이 아직 없어요. 설치(install)를 한 번 더 실행하거나, .env에 GEMINI_API_KEY를 넣으면 Gemini가 녹음을 들어요. "
            "그동안은 녹음 앱에서 글로 바꾼 뒤 공유해 주세요."
        )
    try:
        model = _model()
    except Exception as e:  # 모델 내려받기 실패 등
        _model.cache_clear()
        raise SttUnavailable(f"음성 인식 모델을 준비하지 못했어요. 인터넷을 확인하고 다시 넣어 주세요. [{type(e).__name__}]")
    try:
        segments, _info = model.transcribe(str(path), language="ko", vad_filter=True)
        return "\n".join(s.text.strip() for s in segments if s.text.strip())
    except Exception as e:
        raise SttUnavailable(f"이 녹음 파일은 읽지 못했어요. m4a·mp3·wav인지 확인해 주세요. [{type(e).__name__}]")
