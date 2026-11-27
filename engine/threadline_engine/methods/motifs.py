"""RPC methods. Motifs: the built-in ones and your own."""

from __future__ import annotations

from .. import motifs
from .registry import dispatcher


@dispatcher.method("motifs.list")
def motifs_list() -> list:
    return motifs.list_motifs()


@dispatcher.method("motifs.save")
def motifs_save(name: str, nodes: list, closed: bool = False) -> dict:
    return motifs.save(name, nodes, closed)


@dispatcher.method("motifs.delete")
def motifs_delete(id: str) -> None:  # noqa: A002 - the parameter's name in the protocol
    motifs.delete(id)


@dispatcher.method("motifs.export")
def motifs_export(id: str, dest: str) -> dict:  # noqa: A002
    return motifs.export(id, dest)


@dispatcher.method("motifs.import")
def motifs_import(path: str) -> dict:
    return motifs.import_file(path)
