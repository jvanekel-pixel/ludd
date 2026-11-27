"""RPC methods. Stitch presets: a shape's stitch settings kept under a name."""

from __future__ import annotations

from .. import presets
from .registry import dispatcher


@dispatcher.method("presets.list")
def presets_list() -> list:
    return presets.list_presets()


@dispatcher.method("presets.save")
def presets_save(preset: dict, replace: bool = False) -> dict:
    return presets.save(preset, replace)


@dispatcher.method("presets.delete")
def presets_delete(id: str) -> None:  # noqa: A002 - the parameter's name in the protocol
    presets.delete(id)


@dispatcher.method("presets.export")
def presets_export(id: str, dest: str) -> dict:  # noqa: A002
    return presets.export(id, dest)


@dispatcher.method("presets.import")
def presets_import(path: str) -> dict:
    return presets.import_file(path)
