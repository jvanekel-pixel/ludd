from __future__ import annotations

import sys

from .artimport import child


def main() -> None:
    if options := sys.argv[1:]:
        # The one option there is: be the one-use child artwork import starts to read a PDF or
        # outline wide strokes (artimport/child.py). Anything else is refused, so a copy of the
        # engine started any other way can never read the app's requests as a second engine.
        if options == [child.WORKER_FLAG]:
            sys.exit(child.main())
        print(f"threadline engine: unknown option {options[0]!r}", file=sys.stderr)
        sys.exit(2)
    # Force UTF-8 and LF on every OS so the UI parses the same bytes everywhere.
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # a stray byte must not stop the engine
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("threadline engine ready", file=sys.stderr, flush=True)
    # Imported here: the child starts without loading the rest of the engine.
    from .methods import dispatcher
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
