"""RPC methods. The AI add-on (off by default). The ai package is the only code that talks to a network,
and only when the user turned it on."""

from __future__ import annotations

from .registry import dispatcher


@dispatcher.method("ai.settings")
def ai_settings() -> dict:
    from ..ai import settings

    return settings.public()


@dispatcher.method("ai.save_settings")
def ai_save_settings(patch: dict) -> dict:
    from ..ai import settings

    return settings.save(patch)


@dispatcher.method("ai.set_key")
def ai_set_key(key: str | None = None) -> dict:
    from ..ai import settings

    return settings.set_key(key)


@dispatcher.method("ai.test", background=True)
def ai_test() -> dict:
    from ..ai import providers

    return providers.test_connection()


@dispatcher.method("ai.advisor_preview")
def ai_advisor_preview(layout: dict, images: list | None = None, ids: list | None = None) -> dict:
    """What the Stitch Advisor would send, without sending it."""
    from ..ai import advisor, providers

    provider = providers.require("advisor", "vision")
    req, _ = advisor.build_request(layout, images or [], ids)
    return providers.estimate(req, provider)


@dispatcher.method("ai.advise", background=True)
def ai_advise(layout: dict, images: list | None = None, ids: list | None = None) -> dict:
    from ..ai import advisor

    return advisor.advise(layout, images or [], ids)
