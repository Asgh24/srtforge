"""Entry point: ``python -m srtforge`` or the ``srtforge`` console script."""

from __future__ import annotations

import sys


def main() -> int:
    from srtforge.app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
