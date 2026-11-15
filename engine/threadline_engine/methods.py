"""Engine RPC methods."""

from __future__ import annotations

import platform
import sys

from . import __version__, autotrace, design, fabrics, lettering, profiles, project, threads, trace
from . import layout as layout_module
from .rpc import Dispatcher

dispatcher = Dispatcher()


@dispatcher.method("ping")
def ping() -> str:
    return "pong"


@dispatcher.method("engine.info")
def engine_info() -> dict[str, str]:
    return {
        "version": __version__,
        "python": platform.python_version(),
        "platform": sys.platform,
    }


@dispatcher.method("engine.shutdown")
def engine_shutdown() -> bool:
    """Stop after answering. The app asks this when it quits, so the packaged engine exits by itself
    and deletes its unpacked files (being killed leaves them in the temp folder)."""
    dispatcher.stopping = True
    return True


@dispatcher.method("formats.list")
def formats_list() -> dict:
    return design.formats()


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


@dispatcher.method("machines.list")
def machines_list() -> list:
    return profiles.list_machines()


@dispatcher.method("threads.charts")
def threads_charts() -> list:
    return threads.list_charts()


@dispatcher.method("threads.chart")
def threads_chart(id: str) -> dict:
    return threads.get_chart(id)


@dispatcher.method("threads.import_csv")
def threads_import_csv(path: str, name: str = "", brand: str = "") -> dict:
    return threads.import_csv(path, name, brand)


@dispatcher.method("threads.delete_chart")
def threads_delete_chart(id: str) -> None:
    threads.delete_chart(id)


@dispatcher.method("threads.my_add")
def threads_my_add(spools: list) -> dict:
    return threads.my_add(spools)


@dispatcher.method("threads.my_remove")
def threads_my_remove(spools: list) -> dict:
    return threads.my_remove(spools)


@dispatcher.method("threads.match")
def threads_match(colors: list, chart: str, count: int = 3) -> list:
    return threads.match(colors, chart, count)


@dispatcher.method("layout.render")
def layout_render(layout: dict) -> dict:
    return layout_module.render_summary(layout)


@dispatcher.method("layout.preview_export")
def layout_preview_export(layout: dict, options: dict | None = None, ext: str | None = None) -> dict:
    return layout_module.preview_export(layout, options, ext)


@dispatcher.method("layout.export")
def layout_export(layout: dict, dest: str, options: dict | None = None, keep_existing: bool = False) -> dict:
    return layout_module.export(layout, dest, options, keep_existing)


@dispatcher.method("layout.check", background=True)
def layout_check(layout: dict, heatmap: bool = False) -> dict:
    """Off the main loop, so an edit's render never waits for the checks: only the render (which
    uses the shared caches, and is usually already cached) takes the lock."""
    with dispatcher.lock:
        r = layout_module.render(layout)
    return layout_module.check(layout, heatmap, rendered=r)


@dispatcher.method("layout.split_plan")
def layout_split_plan(layout: dict, hoop: dict, overlap_mm: float = 10.0) -> dict:
    return layout_module.split_plan(layout, hoop, overlap_mm)


@dispatcher.method("layout.export_split")
def layout_export_split(layout: dict, dest: str, hoop: dict, overlap_mm: float = 10.0, options: dict | None = None) -> dict:
    return layout_module.export_split(layout, dest, hoop, overlap_mm, options)


@dispatcher.method("applique.export_svg")
def applique_export_svg(layout: dict, dest: str) -> dict:
    return layout_module.export_applique_svg(layout, dest)


@dispatcher.method("fabrics.list")
def fabrics_list() -> list:
    return fabrics.FABRICS


@dispatcher.method("image.load")
def image_load(path: str) -> dict:
    return project.load_image(path)


@dispatcher.method("project.save")
def project_save(path: str, project_data: dict) -> dict:
    return project.save(path, project_data)


@dispatcher.method("project.open")
def project_open(path: str) -> dict:
    return project.open_project(path)


@dispatcher.method("project.autosave")
def project_autosave(project_data: dict) -> dict:
    return project.autosave(project_data)


@dispatcher.method("project.recovery")
def project_recovery() -> dict | None:
    return project.recovery()


@dispatcher.method("project.restore")
def project_restore() -> dict:
    return project.restore()


@dispatcher.method("project.discard_recovery")
def project_discard_recovery(keep: bool = False) -> None:
    project.discard_recovery(keep)


@dispatcher.method("trace.info")
def trace_info(path: str) -> dict:
    return trace.info(path)


@dispatcher.method("trace.suggest")
def trace_suggest(
    path: str, placement: dict, points: list, step_mm: float = 3.0, mode: str = "auto", closed: bool = False, satin: bool = False
) -> dict:
    return trace.suggest(path, placement, points, step_mm, mode, closed, satin)


@dispatcher.method("shape.offset")
def shape_offset(layout: dict, ids: list, distance_mm: float, spacing: float = 3.0, holes: bool = False) -> dict:
    from . import shapeops

    return shapeops.offset(layout, ids, distance_mm, spacing, holes)


@dispatcher.method("shape.split")
def shape_split(obj: dict, a: list, b: list, spacing: float = 3.0) -> dict:
    from . import shapeops

    return shapeops.split(obj, tuple(a), tuple(b), spacing)


@dispatcher.method("shape.cut_out")
def shape_cut_out(target: dict, cutters: list, spacing: float = 3.0) -> dict:
    from . import shapeops

    return shapeops.cut_out(target, cutters, spacing)


@dispatcher.method("shape.satin_fill")
def shape_satin_fill(outline: list, way: int = 0, tips: list | None = None) -> dict:
    """Fill a closed shape with one satin that turns with it (its two sides, split at its tips;
    `tips`: the two tips chosen by hand)."""
    from .digitize.satinfill import satin_fill

    return satin_fill(outline, way, tips)


@dispatcher.method("shape.merge")
def shape_merge(objs: list, spacing: float = 3.0) -> dict:
    from . import shapeops

    return shapeops.merge(objs, spacing)


@dispatcher.method("library.scan", background=True)
def library_scan(folder: str, recursive: bool = True, query: str = "") -> dict:
    from . import library

    return library.scan(folder, recursive, query)


@dispatcher.method("layout.optimize_jumps")
def layout_optimize_jumps(layout: dict) -> dict:
    """Where each piece starts and ends, so jumps between same-thread pieces are shortest."""
    from .jumps import optimize_jumps

    return optimize_jumps(layout)


@dispatcher.method("text.to_shapes")
def text_to_shapes(item: dict) -> dict:
    """Lettering as drawn shapes, one per letter part, to edit like any other shape."""
    return layout_module.text_to_shapes(item)


@dispatcher.method("text.letter_frame")
def text_letter_frame(item: dict, at: list) -> list:
    """A point on the design (mm) in a text's own unturned frame, where its letters' chosen starts
    and ends are kept."""
    t = layout_module.Transform.from_dict(item.get("transform"))
    from .jumps import _unturn

    return list(_unturn(t, (float(at[0]) - t.x, float(at[1]) - t.y)))


@dispatcher.method("shape.set_end")
def shape_set_end(obj: dict, which: str, at: list) -> dict:
    """Drag a drawn piece's start (green dot) or end (red dot) to `at`: the piece, changed to suit."""
    from .jumps import set_end

    return set_end(obj, which, at)


@dispatcher.method("layout.optimize_order")
def layout_optimize_order(layout: dict) -> dict:
    return layout_module.optimize_order(layout)


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
    from .ai import segment

    return segment.status()


@dispatcher.method("ai.trace_model_download", background=True)
def ai_trace_model_download() -> dict:
    from .ai import segment

    return segment.download()


@dispatcher.method("ai.trace_model_remove")
def ai_trace_model_remove() -> dict:
    from .ai import segment

    return segment.remove()


@dispatcher.method("fonts.list")
def fonts_list() -> list:
    return lettering.list_fonts()


@dispatcher.method("fonts.export_stitch_font")
def fonts_export_stitch_font(font: dict, dest: str, chars: str, cap_height_mm: float = 12.0, style: str = "satin", name: str = "") -> dict:
    return lettering.export_stitch_font(font, dest, chars, cap_height_mm, style, name)


# ---------------------------------------------------------------- AI add-on (off by default) and Help
# The ai package is the only code that talks to a network, and only when the user turned it on.


@dispatcher.method("ai.settings")
def ai_settings() -> dict:
    from .ai import settings

    return settings.public()


@dispatcher.method("ai.save_settings")
def ai_save_settings(patch: dict) -> dict:
    from .ai import settings

    return settings.save(patch)


@dispatcher.method("ai.set_key")
def ai_set_key(key: str | None = None) -> dict:
    from .ai import settings

    return settings.set_key(key)


@dispatcher.method("ai.test", background=True)
def ai_test() -> dict:
    from .ai import providers

    return providers.test_connection()


@dispatcher.method("ai.advisor_preview")
def ai_advisor_preview(layout: dict, images: list | None = None, ids: list | None = None) -> dict:
    """What the Stitch Advisor would send, without sending it."""
    from .ai import advisor, providers

    provider = providers.require("advisor", "vision")
    req, _ = advisor.build_request(layout, images or [], ids)
    return providers.estimate(req, provider)


@dispatcher.method("ai.advise", background=True)
def ai_advise(layout: dict, images: list | None = None, ids: list | None = None) -> dict:
    from .ai import advisor

    return advisor.advise(layout, images or [], ids)


@dispatcher.method("help.search")
def help_search(query: str) -> list:
    from .ai import help

    return help.search(query)


@dispatcher.method("help.preview")
def help_preview(question: str) -> dict:
    from .ai import help, providers

    provider = providers.current("help")
    if isinstance(provider, providers.Off):
        raise providers.AIError("AI answers are off")
    return providers.estimate(help.request(question), provider)


@dispatcher.method("help.ask", background=True)
def help_ask(question: str, use_ai: bool = True) -> dict:
    from .ai import help

    return help.ask(question, use_ai)
