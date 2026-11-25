"""Thin provider-agnostic chat client: openrouter | openai | anthropic."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

# USD per token, used when the API does not report a cost itself.
# OpenRouter list prices checked when the eval was run (see eval/results.md).
PRICES = {
    "anthropic/claude-haiku-4.5": (1e-6, 5e-6),
    "claude-haiku-4-5": (1e-6, 5e-6),
    "openai/gpt-4o-mini": (1.5e-7, 6e-7),
    "gpt-4o-mini": (1.5e-7, 6e-7),
}


@dataclass
class LLMReply:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openrouter").lower()


def model_name() -> str:
    return os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4.5")


def _cost(model: str, pt: int, ct: int) -> float:
    pi, po = PRICES.get(model, (0.0, 0.0))
    return pt * pi + ct * po


def chat(system: str, user: str, image_jpeg: bytes | None = None, max_tokens: int = 2500) -> LLMReply:
    prov, model = provider(), model_name()
    if prov == "anthropic":
        import anthropic

        client = anthropic.Anthropic()
        content: list = []
        if image_jpeg:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                        "data": base64.b64encode(image_jpeg).decode()}})
        content.append({"type": "text", "text": user})
        r = client.messages.create(model=model, max_tokens=max_tokens, temperature=0, system=system,
                                   messages=[{"role": "user", "content": content}])
        pt, ct = r.usage.input_tokens, r.usage.output_tokens
        return LLMReply("".join(b.text for b in r.content if b.type == "text"), pt, ct, _cost(model, pt, ct))

    import openai

    if prov == "openrouter":
        client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
        extra = {"usage": {"include": True}}
    else:
        client = openai.OpenAI()
        extra = {}
    content = []
    if image_jpeg:
        b64 = base64.b64encode(image_jpeg).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({"type": "text", "text": user})
    r = client.chat.completions.create(
        model=model, max_tokens=max_tokens, temperature=0, extra_body=extra,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
    )
    u = r.usage
    pt, ct = u.prompt_tokens, u.completion_tokens
    reported = getattr(u, "cost", None)
    cost = float(reported) if reported is not None else _cost(model, pt, ct)
    return LLMReply(r.choices[0].message.content or "", pt, ct, cost)
