"""Tesseract OCR that keeps word boxes."""
from __future__ import annotations

import os
from dataclasses import dataclass

os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # tesseract threads fight with other work
import pytesseract
from PIL import Image


@dataclass
class Word:
    text: str
    x: int
    y: int
    w: int
    h: int
    conf: float
    line: int  # global line index


@dataclass
class OCRResult:
    words: list[Word]
    text: str
    mean_conf: float


def run_ocr(img: Image.Image, lang: str = "eng", psm: int = 6) -> OCRResult:
    d = pytesseract.image_to_data(
        img, lang=lang, config=f"--psm {psm}", output_type=pytesseract.Output.DICT
    )
    words: list[Word] = []
    line_ids: dict[tuple, int] = {}
    for i, t in enumerate(d["text"]):
        t = t.strip()
        if not t or float(d["conf"][i]) < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        lid = line_ids.setdefault(key, len(line_ids))
        words.append(Word(t, d["left"][i], d["top"][i], d["width"][i], d["height"][i],
                          float(d["conf"][i]), lid))
    lines: dict[int, list[Word]] = {}
    for w in words:
        lines.setdefault(w.line, []).append(w)
    text = "\n".join(" ".join(w.text for w in sorted(ws, key=lambda w: w.x)) for _, ws in sorted(lines.items()))
    mean = sum(w.conf for w in words) / len(words) if words else 0.0
    return OCRResult(words, text, mean)
