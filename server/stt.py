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
            "이 PC에 음성 인식이 아직 없어요. 설치(install)를 한 번 더 실행하면 들어가요. 그동안은 녹음 앱에서 글로 바꾼 뒤 공유해 주세요."
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
