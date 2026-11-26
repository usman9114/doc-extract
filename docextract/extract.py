"""Prompts, JSON parsing and retries for both extraction modes."""
from __future__ import annotations

import json
import re
import time

from pydantic import ValidationError

from . import llm
from .schema import Document, Issue, Result
from .validate import validate

SYSTEM = """You extract structured data from receipts and invoices.
Return ONLY one JSON object, no prose and no markdown fences, with exactly these keys:
vendor_name, vendor_address, date, invoice_number, currency, subtotal, tax, discount,
service_charge, total, line_items.
Rules:
- Copy values exactly as printed. Use null when a field is not on the document. Never guess.
- Money fields are plain JSON numbers in the document's own currency units, no currency
  symbols and no thousands separators. A dot or comma followed by exactly three digits is a
  thousands separator (Rp 60.000 or 60,000 -> 60000). One or two digits after it is a decimal.
- date is ISO YYYY-MM-DD, currency an ISO 4217 code (infer it only from a printed symbol or
  country-specific wording such as Rp -> IDR, else null).
- subtotal is the amount before tax. tax is the tax/VAT amount. discount is a positive number.
  service_charge is a service fee if printed. total is the final amount due on the document, NOT the cash tendered, amount paid or change.
- line_items is a list of {"description", "qty", "unit_price", "amount"}. amount is the line
  total as printed; qty and unit_price are null if not printed. List each purchased item once,
  in order. Do not list tax, totals, payment or change lines as items. Modifier lines that
  belong to an item (toppings, options) are separate items only if they carry their own price.
"""

USER_TEXT = "OCR text of the document (may contain recognition errors):\n\n{ocr}\n\nReturn the JSON object."
USER_IMG = "Extract the data from the attached document image. Return the JSON object."


def parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("no JSON object in reply")
    return json.loads(t[i : j + 1])


def extract(mode: str, ocr_text: str | None = None, image_jpeg: bytes | None = None,
            ocr_conf: float | None = None, retries: int = 2) -> Result:
    """mode 'text' uses OCR text, mode 'vision' sends the image."""
    user = USER_TEXT.format(ocr=ocr_text) if mode == "text" else USER_IMG
    img = image_jpeg if mode == "vision" else None
    t0 = time.time()
    pt = ct = 0
    cost = 0.0
    err = ""
    for attempt in range(1, retries + 2):
        prompt = user if not err else f"{user}\n\nYour previous reply was invalid ({err}). Return valid JSON only."
        reply = llm.chat(SYSTEM, prompt, img)
        pt += reply.prompt_tokens
        ct += reply.completion_tokens
        cost += reply.cost_usd
        try:
            doc = Document.model_validate(parse_json(reply.text))
            break
        except (ValueError, ValidationError) as e:  # json.JSONDecodeError is a ValueError
            err = str(e)[:200]
    else:
        doc = Document()
        v = validate(doc, ocr_conf)
        v.issues.insert(0, Issue(
            field="document", rule="parse", message=f"LLM reply never parsed: {err}"))
        v.needs_review, v.confidence = True, 0.0
        return Result(document=doc, validation=v, mode=mode, model=llm.model_name(vision=mode == "vision"),
                      latency_s=time.time() - t0, prompt_tokens=pt, completion_tokens=ct,
                      cost_usd=cost, attempts=retries + 1)
    return Result(document=doc, validation=validate(doc, ocr_conf), mode=mode, model=llm.model_name(vision=mode == "vision"),
                  latency_s=time.time() - t0, prompt_tokens=pt, completion_tokens=ct,
                  cost_usd=cost, attempts=attempt)
