"""음성 → 글. 집 PC에서 로컬로 돌린다(faster-whisper). 다른 엔진으로 바꿀 때 이 파일만 고친다.

환경 변수
  MALHAN_WHISPER_MODEL : tiny | base | small | medium | large-v3 (기본 small)
  MALHAN_WHISPER_DEVICE: cpu | cuda (기본 cpu)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class SttUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


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
    if not available():
        raise SttUnavailable(
            "이 서버에는 음성 인식이 설치되어 있지 않아요. 'pip install faster-whisper' 후 다시 넣어 주세요."
        )
    segments, _info = _model().transcribe(str(path), language="ko", vad_filter=True)
    return "\n".join(s.text.strip() for s in segments if s.text.strip())
