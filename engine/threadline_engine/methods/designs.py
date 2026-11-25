"""RPC methods. Stitch files: open, export, convert a folder, scan a library."""

from __future__ import annotations

from .. import design
from .registry import dispatcher


@dispatcher.method("design.open")
def design_open(path: str) -> dict:
    return design.open_design(path)


@dispatcher.method("design.preview_export")
def design_preview_export(src: str, options: dict | None = None, ext: str | None = None) -> dict:
    return design.preview_export(src, options, ext)


@dispatcher.method("design.export")
def design_export(src: str, dest: str, options: dict | None = None) -> dict:
    return design.export(src, dest, options)


@dispatcher.method("design.convert_folder")
def design_convert_folder(
    src_dir: str, dest_dir: str, ext: str, recursive: bool = False, options: dict | None = None
) -> dict:
    return design.convert_folder(src_dir, dest_dir, ext, recursive, options)


@dispatcher.method("library.scan", background=True)
def library_scan(folder: str, recursive: bool = True, query: str = "") -> dict:
    from .. import library

    return library.scan(folder, recursive, query)
