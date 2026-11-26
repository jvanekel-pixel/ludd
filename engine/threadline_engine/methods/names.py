"""RPC methods. Lists of names, and name templates."""

from __future__ import annotations

from .. import names as name_lists
from .registry import dispatcher


@dispatcher.method("names.read_list")
def names_read_list(path: str) -> dict:
    """A CSV or text file of names, as columns and rows."""
    return name_lists.read_list(path)


@dispatcher.method("names.list_templates")
def names_list_templates() -> list:
    """The name templates saved in LUDD's data folder."""
    return name_lists.list_templates()


@dispatcher.method("names.save_template")
def names_save_template(name: str, project_data: dict, replace: bool = False) -> dict:
    """Save a design as a name template (one with the same name only when `replace`)."""
    return name_lists.save_template(name, project_data, replace)
