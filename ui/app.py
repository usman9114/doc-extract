"""Streamlit UI: image with OCR boxes on the left, extracted fields on the right."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from PIL import ImageDraw

load_dotenv()
from docextract import export  # noqa: E402
from docextract.pipeline import process_bytes  # noqa: E402

st.set_page_config(page_title="doc-extract", layout="wide")
st.title("Invoices & receipts to clean data")
st.caption("OCR + LLM extraction with validation. Demo on public data (CORD, CC-BY-4.0).")

mode = st.sidebar.radio("Extraction mode", ["text", "vision"],
                        format_func=lambda m: "A: OCR text to LLM" if m == "text" else "B: image to vision LLM",
                        index=0 if os.environ.get("EXTRACT_MODE", "text") == "text" else 1)
up = st.file_uploader("Upload a receipt or invoice (JPG, PNG, PDF)", type=["jpg", "jpeg", "png", "pdf"])
sample = Path("assets/sample_receipt.jpg")
if up is None and sample.exists() and st.button("Use sample receipt"):
    st.session_state["sample"] = True
data, name = (up.getvalue(), up.name) if up else ((sample.read_bytes(), sample.name)
                                                  if st.session_state.get("sample") else (None, ""))

if data:
    key = (name, len(data), mode)
    if st.session_state.get("key") != key:
        with st.spinner("Running OCR and extraction..."):
            st.session_state["out"], st.session_state["key"] = process_bytes(data, name, mode), key
    out = st.session_state["out"]
    r, doc, val = out.result, out.result.document, out.result.validation
    left, right = st.columns(2)
    with left:
        img = out.image.copy()
        if out.ocr:
            dr = ImageDraw.Draw(img)
            for w in out.ocr.words:
                dr.rectangle([w.x, w.y, w.x + w.w, w.y + w.h], outline=(220, 30, 30), width=2)
        st.image(img, caption="OCR word boxes" if out.ocr else "Input (vision mode, no OCR boxes)",
                 use_container_width=True)
    with right:
        if val.needs_review:
            st.error(f"Needs review (confidence {val.confidence:.2f})")
            for i in val.issues:
                st.write(f"- **{i.field}**: {i.message}")
        else:
            st.success(f"Auto-approved (confidence {val.confidence:.2f})")
        bad = val.bad_fields
        flag = lambda f: " (check)" if f in bad else ""  # noqa: E731
        fields = {k: getattr(doc, k) for k in ["vendor_name", "date", "invoice_number", "currency",
                                               "subtotal", "tax", "discount", "service_charge", "total"]}
        st.table(pd.DataFrame({"field": [k + flag(k) for k in fields],
                               "value": ["" if v is None else str(v) for v in fields.values()]}).set_index("field"))
        items = pd.DataFrame([i.model_dump() for i in doc.line_items])
        if not items.empty:
            st.dataframe(items, use_container_width=True)
        st.caption(f"{r.model} | {r.latency_s:.1f}s | {r.prompt_tokens}+{r.completion_tokens} tokens | ${r.cost_usd:.5f}")
        st.download_button("Download CSV", export.to_csv(r), "extraction.csv", "text/csv")
        st.download_button("Download JSON", export.to_json(r), "extraction.json", "application/json")
