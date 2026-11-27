"""RPC methods. Stitch presets: a shape's stitch settings kept under a name."""

from __future__ import annotations

from ..layout import LayoutError
from .registry import dispatcher


@dispatcher.method("presets.list")
def presets_list() -> list:
    raise LayoutError("not built yet")


@dispatcher.method("presets.save")
def presets_save(preset: dict, replace: bool = False) -> dict:
    raise LayoutError("not built yet")


@dispatcher.method("presets.delete")
def presets_delete(id: str) -> None:  # noqa: A002 - the parameter's name in the protocol
    raise LayoutError("not built yet")


@dispatcher.method("presets.export")
def presets_export(id: str, dest: str) -> dict:  # noqa: A002
    raise LayoutError("not built yet")


@dispatcher.method("presets.import")
def presets_import(path: str) -> dict:
    raise LayoutError("not built yet")
