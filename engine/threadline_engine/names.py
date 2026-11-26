"""Reading a list of names for "One file per name" (P5-D1)."""

from __future__ import annotations

from typing import Any


class NamesError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


def read_list(path: str) -> dict[str, Any]:
    """A CSV or text file of names: {"columns": [str], "rows": [[str]], "skipped": int}."""
    raise NamesError("Reading a list of names isn't built yet")
