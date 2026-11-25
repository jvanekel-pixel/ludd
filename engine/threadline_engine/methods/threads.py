"""RPC methods. Thread charts, my threads and color matching."""

from __future__ import annotations

from .. import threads
from .registry import dispatcher


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
