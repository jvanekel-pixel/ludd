"""RPC methods. Machines and fabrics."""

from __future__ import annotations

from .. import fabrics, profiles
from .registry import dispatcher


@dispatcher.method("machines.list")
def machines_list() -> list:
    return profiles.list_machines()


@dispatcher.method("fabrics.list")
def fabrics_list() -> list:
    return fabrics.FABRICS
