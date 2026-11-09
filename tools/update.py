"""켜기 전에 최신 버전으로 맞춘다. run.sh / run.bat / 켜기.command가 run.py보다 먼저 부른다. 본체는 server/updater.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import updater  # noqa: E402

if __name__ == "__main__":
    try:
        sys.exit(updater.main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
