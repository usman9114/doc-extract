"""Render side_by_side.png and cover_1600x1200.png from the eval summary and one pipeline run."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from docextract.pipeline import process_image  # noqa: E402

BG, FG, DIM, GREEN, RED = (15, 17, 21), (240, 242, 245), (150, 158, 170), (61, 220, 151), (240, 90, 90)


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def side_by_side():
    out = process_image(Image.open(ROOT / "assets/sample_receipt.png").convert("RGB"), "text")
    img = out.image.copy()
    d = ImageDraw.Draw(img)
    for w in out.ocr.words:
        d.rectangle([w.x, w.y, w.x + w.w, w.y + w.h], outline=(230, 30, 30), width=2)
    H = 900
    img = img.resize((int(img.width * H / img.height), H))
    doc, val = out.result.document, out.result.validation
    W = img.width + 760
    canvas = Image.new("RGB", (W, H + 80), BG)
    canvas.paste(img, (20, 70))
    c = ImageDraw.Draw(canvas)
    c.text((20, 20), "OCR word boxes (Tesseract)", font=font(22, True), fill=FG)
    x = img.width + 60
    c.text((x, 20), "Extracted fields + validation", font=font(22, True), fill=FG)
    y = 80
    for k in ["currency", "subtotal", "tax", "total"]:
        bad = k in val.bad_fields
        c.text((x, y), f"{k}", font=font(20), fill=DIM)
        c.text((x + 200, y), str(getattr(doc, k)), font=font(20, True), fill=RED if bad else FG)
        y += 38
    y += 10
    c.text((x, y), "line_items", font=font(20), fill=DIM)
    for it in doc.line_items:
        c.text((x + 200, y), f"{it.description}  {it.amount:g}", font=font(20, True), fill=FG)
        y += 38
    y += 30
    c.rounded_rectangle([x, y, W - 30, y + 150], 10, outline=RED if val.needs_review else GREEN, width=3)
    c.text((x + 18, y + 14), "NEEDS REVIEW" if val.needs_review else "AUTO-APPROVED", font=font(24, True),
           fill=RED if val.needs_review else GREEN)
    for n, i in enumerate(val.issues[:2]):
        c.text((x + 18, y + 56 + 36 * n), i.message[:52], font=font(17), fill=FG)
    canvas.save(ROOT / "assets/side_by_side.png")
    print(doc.total, [i.message for i in val.issues])


def cover():
    S = {s["mode"]: s for s in json.loads((ROOT / "eval/summary.json").read_text())}
    A, B = S["text"], S["vision"]
    im = Image.new("RGB", (1600, 1200), BG)
    d = ImageDraw.Draw(im)
    d.text((100, 130), "Invoices & receipts", font=font(92, True), fill=FG)
    d.text((100, 245), "→ clean data", font=font(92, True), fill=GREEN)
    d.text((100, 390), "OCR + LLM extraction with validation and a review flag", font=font(34), fill=DIM)
    stats = [(f"{100 * B['total_acc']:.0f}%", "total amount correct\n(vision mode)"),
             (f"{100 * B['auto_approved_pct']:.0f}%", "auto-approved,\nrest flagged for review"),
             (f"${B['cost_per_100']:.2f}", "LLM cost per 100\nreceipts (vision)")]
    for n, (big, small) in enumerate(stats):
        x = 100 + n * 480
        d.rounded_rectangle([x, 560, x + 430, 860], 20, fill=(26, 29, 36))
        d.text((x + 36, 600), big, font=font(100, True), fill=GREEN)
        d.multiline_text((x + 36, 740), small, font=font(28), fill=FG, spacing=8)
    d.text((100, 940), f"Measured on {B['docs']} held-out CORD receipts, claude-haiku-4.5. "
                       f"OCR-text mode: {100 * A['total_acc']:.0f}% totals, ${A['cost_per_100']:.2f} per 100.",
           font=font(26), fill=DIM)
    d.text((100, 1010), "Tesseract OCR  |  Pydantic schema  |  FastAPI  |  Streamlit  |  Docker", font=font(26), fill=DIM)
    d.text((100, 1090), "Demo on public data (CORD, CC-BY-4.0)", font=font(24), fill=DIM)
    im.save(ROOT / "assets/cover_1600x1200.png")


if __name__ == "__main__":
    side_by_side()
    cover()
