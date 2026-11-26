"""Thin provider-agnostic chat client: zai | openrouter | openai | anthropic."""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass

# USD per token, used when the API does not report a cost itself.
# OpenRouter list prices checked when the eval was run (see eval/results.md).
PRICES = {
    "anthropic/claude-haiku-4.5": (1e-6, 5e-6),
    "claude-haiku-4-5": (1e-6, 5e-6),
    "openai/gpt-4o-mini": (1.5e-7, 6e-7),
    "gpt-4o-mini": (1.5e-7, 6e-7),
    # Z.ai Flash models are free: https://docs.z.ai/guides/overview/pricing
    "glm-4.5-flash": (0.0, 0.0),
    "glm-4.7-flash": (0.0, 0.0),
    "glm-4.6v-flash": (0.0, 0.0),
}

DEFAULT_MODELS = {  # (text model, vision model) per provider
    "zai": ("glm-4.5-flash", "glm-4.6v-flash"),
    "openrouter": ("anthropic/claude-haiku-4.5", "anthropic/claude-haiku-4.5"),
    "anthropic": ("claude-haiku-4-5", "claude-haiku-4-5"),
    "openai": ("gpt-4o-mini", "gpt-4o-mini"),
}
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"


@dataclass
class LLMReply:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "zai").lower()


def model_name(vision: bool = False) -> str:
    """LLM_MODEL for text extraction, LLM_VISION_MODEL for image input (falls back to LLM_MODEL)."""
    text_default, vision_default = DEFAULT_MODELS.get(provider(), DEFAULT_MODELS["zai"])
    text = os.environ.get("LLM_MODEL") or text_default
    if vision:
        return os.environ.get("LLM_VISION_MODEL") or (os.environ.get("LLM_MODEL") or vision_default)
    return text


def _cost(model: str, pt: int, ct: int) -> float:
    pi, po = PRICES.get(model, (0.0, 0.0))
    return pt * pi + ct * po


def chat(system: str, user: str, image_jpeg: bytes | None = None, max_tokens: int = 1800) -> LLMReply:
    """One call with retries on rate limits / transient credit-reservation errors."""
    tries = int(os.environ.get("LLM_MAX_TRIES", "8"))
    for n in range(tries):
        try:
            return _chat(system, user, image_jpeg, max_tokens)
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "status_code", None)
            overloaded = "1305" in str(e) or "overloaded" in str(e).lower()
            if n == tries - 1 or not (overloaded or code in (402, 429, 500, 502, 503, 529, None)):
                raise
            time.sleep(min(60, 3 * 2**n))


def _chat(system: str, user: str, image_jpeg: bytes | None = None, max_tokens: int = 2500) -> LLMReply:
    prov, model = provider(), model_name(vision=image_jpeg is not None)
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

    if prov == "zai":
        client = openai.OpenAI(base_url=ZAI_BASE_URL, api_key=os.environ.get("ZAI_API_KEY") or "missing")
        extra = {"thinking": {"type": "disabled"}}
    elif prov == "openrouter":
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
    if not r.choices:  # some providers return an error body with HTTP 200
        raise RuntimeError(f"empty response: {getattr(r, 'error', None) or r}")
    u = r.usage
    pt, ct = u.prompt_tokens, u.completion_tokens
    reported = getattr(u, "cost", None)
    cost = float(reported) if reported is not None else _cost(model, pt, ct)
    return LLMReply(r.choices[0].message.content or "", pt, ct, cost)
