import io

from PIL import Image, ImageDraw

from docextract.preprocess import load_pages


def test_multipage_pdf_renders():
    pages = []
    for n in range(3):
        im = Image.new("RGB", (400, 300), "white")
        ImageDraw.Draw(im).text((20, 20), f"page {n}", fill="black")
        pages.append(im)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:])
    out = load_pages(buf.getvalue(), "x.pdf")
    assert len(out) == 3 and all(p.mode == "RGB" and p.width > 400 for p in out)
