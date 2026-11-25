"""Load images/PDFs, fix rotation, light cleanup."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

PDF_DPI = 200


def load_pages(data: bytes, filename: str = "") -> list[Image.Image]:
    """Return one RGB image per page (PDFs are rendered, multipage supported)."""
    if data[:5] == b"%PDF-" or filename.lower().endswith(".pdf"):
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        pages = [pdf[i].render(scale=PDF_DPI / 72).to_pil().convert("RGB") for i in range(len(pdf))]
        return pages
    img = Image.open(io.BytesIO(data))
    n = getattr(img, "n_frames", 1)
    pages = []
    for i in range(n):
        img.seek(i)
        pages.append(img.convert("RGB"))
    return pages


def estimate_skew(gray: np.ndarray) -> float:
    """Angle (degrees) of the dominant text direction, 0 if unsure."""
    h, w = gray.shape
    scale = 800 / max(h, w)
    small = cv2.resize(gray, (int(w * scale), int(h * scale))) if scale < 1 else gray
    bw = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    bw = cv2.dilate(bw, np.ones((3, 15), np.uint8))  # merge letters into text lines
    pts = cv2.findNonZero(bw)
    if pts is None or len(pts) < 500:
        return 0.0
    angle = cv2.minAreaRect(pts)[-1]
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    return float(angle)


def deskew(img: Image.Image, max_angle: float = 10.0) -> Image.Image:
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    angle = estimate_skew(gray)
    if abs(angle) < 0.7 or abs(angle) > max_angle:
        return img
    arr = np.array(img)
    h, w = arr.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    out = cv2.warpAffine(arr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(out)


def denoise(img: Image.Image) -> Image.Image:
    return Image.fromarray(cv2.fastNlMeansDenoisingColored(np.array(img), None, 5, 5, 5, 15))


def preprocess(img: Image.Image, do_deskew: bool = True, do_denoise: bool = False) -> Image.Image:
    if do_deskew:
        img = deskew(img)
    if do_denoise:
        img = denoise(img)
    return img


def downscale_jpeg(img: Image.Image, max_side: int = 1024, quality: int = 85) -> bytes:
    """Compact JPEG for vision-LLM input."""
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def load_path(path: str | Path) -> list[Image.Image]:
    p = Path(path)
    return load_pages(p.read_bytes(), p.name)
