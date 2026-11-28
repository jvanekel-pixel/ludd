"""RPC methods. Artwork import (SVG, DXF, PDF): a preview of the shapes it would become."""

from __future__ import annotations

from .registry import dispatcher


@dispatcher.method("art.preview", background=True, newest_wins=True)
def art_preview(path: str, options: dict | None = None) -> dict:
    """{size_mm, scale_note, shapes, skipped, warnings, pages} for the artwork at `path`; nothing
    is added to a design here (the app adds the shapes you accept). Options: width_mm (null: the
    file's real size), strokes ("auto", "lines", "satins"), spacing_mm, closed_as_fills (DXF),
    page (PDF, from 0), keep_background (the flagged background counts toward the size).

    Only one preview runs at a time: a newer one stops an older one, which then answers that it
    was replaced. The time limit counts from when the request came in."""
    # Imported here: svgelements and ezdxf load only when artwork is imported (PDFium only in the
    # child process that reads a PDF).
    from ..artimport import Deadline, preview

    ticket = dispatcher.ticket()
    deadline = Deadline(replaced=ticket.replaced, since=ticket.arrived) if ticket else None
    return preview(path, options, deadline)
