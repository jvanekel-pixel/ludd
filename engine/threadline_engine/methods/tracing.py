"""RPC methods. Tracing pictures, and the optional AI tracing model."""

from __future__ import annotations

from .. import autotrace, trace
from .registry import dispatcher


@dispatcher.method("trace.info")
def trace_info(path: str) -> dict:
    return trace.info(path)


@dispatcher.method("trace.suggest")
def trace_suggest(
    path: str, placement: dict, points: list, step_mm: float = 3.0, mode: str = "auto", closed: bool = False, satin: bool = False
) -> dict:
    return trace.suggest(path, placement, points, step_mm, mode, closed, satin)


@dispatcher.method("trace.digitize_all", background=True)
def trace_digitize_all(path: str, placement: dict, spacing_mm: float = 3.0, spread: int = 5, outlines: bool = True,
                       skip_background: bool = True) -> dict:
    return autotrace.digitize_all(path, placement, spacing_mm, spread, outlines, skip_background)


@dispatcher.method("trace.region", background=True)
def trace_region(path: str, placement: dict, at: list, spacing_mm: float = 3.0, add: list | None = None,
                 subtract: list | None = None, spread: int = 5, use_ai: bool = False, taken: list | None = None) -> dict:
    return autotrace.region(path, placement, at, spacing_mm, add, subtract, spread, use_ai, taken)


# AI tracing model (optional): only downloaded when the user presses Download in Settings.
@dispatcher.method("ai.trace_model")
def ai_trace_model() -> dict:
    from ..ai import segment

    return segment.status()


@dispatcher.method("ai.trace_model_download", background=True)
def ai_trace_model_download() -> dict:
    from ..ai import segment

    return segment.download()


@dispatcher.method("ai.trace_model_remove")
def ai_trace_model_remove() -> dict:
    from ..ai import segment

    return segment.remove()
