"""Thin wrapper around the chat LLM. One place to change models or providers."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from config import settings, require_openai_key


@lru_cache(maxsize=1)
def chat_llm(temperature: float = 0.0) -> ChatOpenAI:
    require_openai_key()
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )


def call_json(system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
    """Ask the model and parse a JSON object out of the reply.

    We use response_format=json_object — supported on gpt-4o-class models —
    and fall back to a tolerant parse if the model wraps it in fences.
    """
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    resp = llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    text = (resp.content or "").strip()
    return _loose_json(text)


def call_text(system: str, user: str, *, temperature: float = 0.2) -> str:
    resp = chat_llm(temperature=temperature).invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return (resp.content or "").strip()


def _loose_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        # strip ``` fences
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last-ditch: find first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
