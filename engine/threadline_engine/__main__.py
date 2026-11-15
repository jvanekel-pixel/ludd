from __future__ import annotations

import sys

from .methods import dispatcher


def main() -> None:
    # Force UTF-8 and LF on every OS so the UI parses the same bytes everywhere.
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # a stray byte must not stop the engine
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("threadline engine ready", file=sys.stderr, flush=True)
    from .cleanup import sweep_in_background

    sweep_in_background()  # folders left behind by engines that were killed
    from . import kept

    try:
        kept.prune()  # private copies of files not used for months (before anything is opened)
    except OSError:
        pass
    dispatcher.serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
