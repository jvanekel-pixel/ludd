"""Engine RPC methods, one file per area (it was one module, methods.py, until Phase 3).

A new RPC method goes in the group file for its area, and its name goes in
engine/tests/snapshots/rpc_methods.json. Imports that a method makes inside its body stay there:
they keep the frozen engine's start-up fast.

Every group is imported by name below (no scanning: PyInstaller must see each import).
"""

from __future__ import annotations

from .registry import dispatcher
from . import core, designs, machines, threads, layouts, projects, tracing, shapes, text, ai, help, repair  # noqa: F401,E402
from . import fonts, names  # noqa: F401,E402

__all__ = ["dispatcher"]
