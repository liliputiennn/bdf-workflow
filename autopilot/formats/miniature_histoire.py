"""Miniature de la chaîne Histoire : la miniature standard au thème « parchemin ». Usage : python autopilot/formats/miniature_histoire.py <id> [options de miniature.py]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import miniature  # noqa: E402


def main() -> int:
    if "--theme" not in sys.argv:
        sys.argv += ["--theme", "parchemin"]
    return miniature.main()


if __name__ == "__main__":
    raise SystemExit(main())
