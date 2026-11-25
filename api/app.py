"""FastAPI service: POST /extract."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

load_dotenv()

from docextract import export  # noqa: E402
from docextract.pipeline import process_bytes  # noqa: E402

app = FastAPI(title="doc-extract", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/extract")
async def extract_endpoint(file: UploadFile = File(...), mode: str = Query(None, pattern="^(text|vision)$"),
                           format: str = Query("json", pattern="^(json|csv)$")):
    """Upload a receipt/invoice (image or PDF). Returns the extracted fields, the validation report
    (issues, needs_review, confidence) and run stats. `format=csv` returns a CSV instead."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    mode = mode or os.environ.get("EXTRACT_MODE", "text")
    try:
        out = process_bytes(data, file.filename or "", mode)
    except Exception as e:  # unreadable file, LLM outage, ...
        raise HTTPException(422, f"could not process document: {e}") from e
    if format == "csv":
        return PlainTextResponse(export.to_csv(out.result), media_type="text/csv")
    return out.result.model_dump()
