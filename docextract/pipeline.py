"""End-to-end: file bytes -> Result (+ OCR words for display)."""
from __future__ import annotations

import time
from dataclasses import dataclass

from PIL import Image

from .extract import extract
from .ocr import OCRResult, run_ocr
from .preprocess import downscale_jpeg, load_pages, preprocess
from .schema import Result


@dataclass
class Output:
    result: Result
    image: Image.Image
    ocr: OCRResult | None


def process_image(img: Image.Image, mode: str = "text") -> Output:
    t0 = time.time()
    img = preprocess(img)
    ocr = run_ocr(img) if mode == "text" else None
    ocr_time = time.time() - t0
    if mode == "text":
        res = extract("text", ocr_text=ocr.text, ocr_conf=ocr.mean_conf)
    else:
        res = extract("vision", image_jpeg=downscale_jpeg(img))
    res.latency_s += ocr_time
    return Output(res, img, ocr)


def process_bytes(data: bytes, filename: str = "", mode: str = "text") -> Output:
    """Multipage documents: pages are stacked vertically into one image (fine for receipts and
    short invoices; split per page for long documents)."""
    pages = load_pages(data, filename)
    if len(pages) > 1:
        w = max(p.width for p in pages)
        img = Image.new("RGB", (w, sum(p.height for p in pages)), "white")
        y = 0
        for p in pages:
            img.paste(p, (0, y))
            y += p.height
    else:
        img = pages[0]
    return process_image(img, mode)
