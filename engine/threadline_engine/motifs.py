"""Your own motifs, kept as files in LUDD's data folder (motifs/<name>.json). Not built yet."""

from __future__ import annotations

from typing import Any


class MotifError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


def _not_built() -> MotifError:
    return MotifError("not built yet")


def list_motifs() -> list[dict[str, Any]]:
    """The built-in motifs and your own: [{"id", "name", "builtin", "unit"}]."""
    raise _not_built()


def save(name: str, nodes: list, closed: bool = False) -> dict[str, Any]:
    """Keep a drawn line as a motif of your own: {"id", "name", "unit"}."""
    raise _not_built()


def delete(motif_id: str) -> None:
    """Delete one of your own motifs."""
    raise _not_built()


def export(motif_id: str, dest: str) -> dict[str, Any]:
    """Save a motif as a file: {"path"}."""
    raise _not_built()


def import_file(path: str) -> dict[str, Any]:
    """Add a motif from a file: {"id", "name", "unit"}."""
    raise _not_built()
