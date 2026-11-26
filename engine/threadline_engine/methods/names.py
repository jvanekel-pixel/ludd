"""RPC methods. Lists of names."""

from __future__ import annotations

from .. import names as name_lists
from .registry import dispatcher


@dispatcher.method("names.read_list")
def names_read_list(path: str) -> dict:
    """A CSV or text file of names, as columns and rows."""
    return name_lists.read_list(path)
