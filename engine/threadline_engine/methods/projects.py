"""RPC methods. Projects and pictures: save, open, autosave and recovery."""

from __future__ import annotations

from .. import project
from .registry import dispatcher


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
