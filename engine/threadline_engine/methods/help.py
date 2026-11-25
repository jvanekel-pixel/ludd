"""RPC methods. Help: search the manual, and AI answers when they are on."""

from __future__ import annotations

from .registry import dispatcher


@dispatcher.method("help.search")
def help_search(query: str) -> list:
    from ..ai import help

    return help.search(query)


@dispatcher.method("help.preview")
def help_preview(question: str) -> dict:
    from ..ai import help, providers

    provider = providers.current("help")
    if isinstance(provider, providers.Off):
        raise providers.AIError("AI answers are off")
    return providers.estimate(help.request(question), provider)


@dispatcher.method("help.ask", background=True)
def help_ask(question: str, use_ai: bool = True) -> dict:
    from ..ai import help

    return help.ask(question, use_ai)
