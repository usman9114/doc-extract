"""Business rules on extracted data. Pure functions, no LLM."""
from __future__ import annotations

from datetime import datetime

from .schema import Document, Issue, Validation

# Common ISO 4217 codes; extend as needed.
CURRENCIES = set(
    "USD EUR GBP IDR JPY CNY INR AUD CAD CHF SGD MYR THB VND PHP KRW HKD NZD SEK NOK DKK PLN CZK HUF "
    "RON TRY BRL MXN ZAR AED SAR ILS RUB UAH".split()
)


# Tesseract averages ~50 on phone photos of thermal receipts; flag only clearly bad scans.
OCR_CONF_MIN = 40


def _close(a: float, b: float, rel: float = 0.01, abs_tol: float = 0.011) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))


def validate(doc: Document, ocr_conf: float | None = None) -> Validation:
    issues: list[Issue] = []

    def bad(field: str, rule: str, msg: str):
        issues.append(Issue(field=field, rule=rule, message=msg))

    if doc.total is None:
        bad("total", "required", "total is missing")
    elif doc.total <= 0:
        bad("total", "positive", f"total {doc.total} is not positive")

    items = [i for i in doc.line_items if i.amount is not None]
    if not doc.line_items:
        bad("line_items", "required", "no line items found")
    s = sum(i.amount for i in items) if items else None

    if s is not None and doc.subtotal is not None and not _close(s, doc.subtotal):
        bad("subtotal", "items_sum", f"line items sum to {s:g} but subtotal is {doc.subtotal:g}")

    base = doc.subtotal if doc.subtotal is not None else s
    if base is not None and doc.total is not None:
        expect = base + (doc.tax or 0) + (doc.service_charge or 0) - abs(doc.discount or 0)
        if not _close(expect, doc.total):
            bad("total", "sum", f"subtotal {base:g} + tax {doc.tax or 0:g} + service {doc.service_charge or 0:g}"
                                f" - discount {abs(doc.discount or 0):g} = {expect:g}, but total is {doc.total:g}")

    for n, it in enumerate(doc.line_items, 1):
        if it.qty is not None and it.unit_price is not None and it.amount is not None:
            if not _close(it.qty * it.unit_price, it.amount):
                bad(f"line_items[{n}]", "qty_x_price",
                    f"{it.qty:g} x {it.unit_price:g} = {it.qty * it.unit_price:g}, but amount is {it.amount:g}")

    if doc.date:
        try:
            datetime.strptime(doc.date, "%Y-%m-%d")
        except ValueError:
            bad("date", "parse", f"'{doc.date}' is not a valid YYYY-MM-DD date")
    if doc.currency and doc.currency.upper() not in CURRENCIES:
        bad("currency", "iso", f"'{doc.currency}' is not a known ISO 4217 code")

    conf = 1.0 - 0.25 * len({i.field.split("[")[0] for i in issues})
    if ocr_conf is not None:
        if ocr_conf < OCR_CONF_MIN:
            bad("document", "ocr_conf", f"mean OCR confidence is low ({ocr_conf:.0f}/100)")
        conf *= min(1.0, ocr_conf / 80)
    conf = round(max(0.0, min(1.0, conf)), 2)
    return Validation(issues=issues, needs_review=bool(issues), confidence=conf)
