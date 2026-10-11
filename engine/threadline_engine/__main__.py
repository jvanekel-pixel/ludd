from __future__ import annotations

import sys

from .methods import dispatcher


def main() -> None:
    # Force UTF-8 and LF on every OS so the UI parses the same bytes everywhere.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("threadline engine ready", file=sys.stderr, flush=True)
    dispatcher.serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
