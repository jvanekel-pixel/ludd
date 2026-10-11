"""Help: search the user guide (always works, no AI), and with AI on, answer in plain words
using only the guide's sections that match the question."""

from __future__ import annotations

import re
from typing import Any

from .helpdocs import GUIDE
from .providers import Off, Request, current

STOP = set("a an the and or of to in on for with is are be it its this that how do does can i my me you your what why when where which "
           "from at by as not no if so up out about into".split())

SYSTEM = """You are the help assistant inside LUDD, a free embroidery program. Answer the user's question
using only the guide sections given. Be brief and friendly, in plain words for a beginner, with the exact
button names and shortcuts from the guide. If the guide doesn't cover it, say so and suggest the closest
thing it does cover. Never invent features."""


def sections() -> list[tuple[str, str]]:
    out = []
    for block in GUIDE.strip().split("\n## "):
        title, _, body = block.lstrip("# ").partition("\n")
        out.append((title.strip(), body.strip()))
    return out


def _words(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in STOP and len(w) > 1]


def _stem(w: str) -> str:
    """Light stemming, so "update", "updates" and "updated" match, as do "cut" and "cutting"."""
    if len(w) <= 3:
        return w
    s = re.sub(r"(ing|ed|es|s)$", "", w) if not w.endswith("ss") else w
    s = re.sub(r"e$", "", s) or s
    if len(s) > 3 and s[-1] == s[-2] and s[-1] not in "aeiou":  # cutt -> cut
        s = s[:-1]
    return s or w


def search(query: str, limit: int = 4) -> list[dict[str, str]]:
    q = set(_words(query))
    if not q:
        return []
    scored = []
    for title, body in sections():
        tw, bw = _words(title), _words(body)
        score = 3 * sum(1 for w in q if w in tw) + sum(1 for w in bw if w in q) / (1 + len(bw) / 120)
        if score > 0:
            scored.append((score, title, body))
    scored.sort(key=lambda t: -t[0])
    return [{"title": t, "text": b} for _, t, b in scored[:limit]]


def request(question: str) -> Request:
    found = search(question) or [{"title": t, "text": b} for t, b in sections()[:2]]
    guide = "\n\n".join(f"## {s['title']}\n{s['text']}" for s in found)
    return Request(system=SYSTEM, text=f"Guide sections:\n\n{guide}\n\nQuestion: {question.strip()}", max_tokens=600)


def ask(question: str, use_ai: bool = True) -> dict[str, Any]:
    """Matching guide sections, plus an AI answer when AI and the Help feature are on."""
    question = (question or "").strip()[:500]
    found = search(question)
    result: dict[str, Any] = {"sections": found, "answer": None, "ai": False}
    if not question or not use_ai:
        return result
    provider = current("help")
    if isinstance(provider, Off):
        return result
    result["answer"] = provider.ask(request(question)).strip()
    result["ai"] = True
    return result
