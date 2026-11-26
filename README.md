<p align="center"><img src="assets/banner.webp" alt="doc-extract banner (illustration)" width="100%"></p>

# doc-extract

Turn invoices and receipts into validated, structured data with OCR + LLMs.

![demo](assets/demo.gif)

## The problem

Typing data from receipts and invoices into a system is slow, and plain OCR output is messy text with no structure and no sanity checks. This repo turns a photo or PDF into a strict JSON record, checks that the numbers add up, and flags the documents a human should look at.

## How it works

```
PDF / image
  -> pre-processing   PDF to image (multipage), deskew, optional denoise
  -> OCR              Tesseract, word boxes kept (drawn in the UI)
  -> LLM extraction   strict Pydantic schema, JSON retries on invalid output
        mode A: OCR text -> LLM        mode B: image -> vision LLM
  -> validation       line items vs subtotal, subtotal + tax + service - discount vs total,
                      qty x unit price vs amount, date parses, ISO currency
  -> confidence + "needs review" flag with reasons
  -> export           JSON, CSV, optional append to a Google Sheet
```

- `docextract/` is the package: `preprocess.py`, `ocr.py`, `extract.py` (prompt, schema, retries), `validate.py`, `export.py`, `llm.py`.
- `api/app.py`: FastAPI, `POST /extract` (file upload, `?mode=text|vision`, `?format=json|csv`).
- `ui/app.py`: Streamlit, image with OCR boxes on the left, fields on the right, failing fields marked, CSV and JSON download.
- `eval/run_eval.py`: field-level accuracy, mode A vs B.
- The LLM backend is chosen with env vars: `LLM_PROVIDER=zai|openrouter|anthropic|openai`, `LLM_MODEL` (text) and `LLM_VISION_MODEL` (images). The default is Z.ai's free GLM Flash models (`glm-4.5-flash` for text, `glm-4.6v-flash` for images).

![side by side](assets/side_by_side.png)

The receipt above is a real eval case: the model read the cash tendered line as the subtotal (499000), the line items add up to 198000, and the validator flags it for review instead of letting a wrong number through.

## Results

Data: 50 receipts drawn with a fixed seed (42) from the CORD v2 test split, the same 50 for every model. They were never used while writing prompts or choosing thresholds; those were tuned on a handful of receipts from the validation split. OCR is Tesseract 5. Everything here is copied from [`eval/results.md`](eval/results.md), produced by `python -m eval.run_eval` (per-document rows in `eval/results*.csv`).

| Metric | A: GLM-4.5-Flash (OCR text) | A: Haiku 4.5 (OCR text) | B: Haiku 4.5 (image) |
|---|---|---|---|
| Total amount correct | 53% | 55% | 90% |
| Subtotal correct (33 receipts that have one) | 42% | 48% | 85% |
| Tax correct (23 receipts that have one) | 39% | 39% | 74% |
| Line items F1 (amount + description match) | 41% | 44% | 83% |
| Item quantity correct (matched items) | 76% | 70% | 96% |
| Receipts with total, subtotal and tax all correct | 46% | 50% | 76% |
| Receipts with everything correct incl. all line items | 14% | 20% | 60% |
| Flagged for review | 66% | 68% | 26% |
| Auto-approved receipts with total, subtotal and tax all correct | 76% | 88% | 95% |
| Median latency per receipt | 9.3 s | 2.6 s | 2.9 s |
| LLM cost per 100 receipts | US$0.00 (free tier) | US$0.15 | US$0.24 |

GLM ran on the Z.ai API (free Flash models, see the [pricing page](https://docs.z.ai/guides/overview/pricing); token counts are still recorded in the results). Haiku ran through OpenRouter, and its cost is what OpenRouter reported per call. **The GLM image mode (`glm-4.6v-flash`) is not measured**: for about an hour of retries every request to it returned "service overloaded" (code 1305), so there is no column for it. The command to fill it in later is under "Run it".

![accuracy](assets/accuracy_chart.png)

What this says, honestly:

- On the same OCR text, free GLM-4.5-Flash lands within a few points of Haiku on totals (53% vs 55%), at no cost but with slower responses (median 9.3 s, partly waiting out the free tier's overload retries).
- Vision beats OCR-then-LLM by a wide margin here, mostly because CORD is phone photos of crumpled thermal receipts and Tesseract reads them badly (16 of 50 receipts yielded no usable total in mode A with Haiku, 15 with GLM). On clean scans or digital PDFs, mode A is much closer and cheaper; this eval does not measure that.
- Validation earns its keep. Haiku mode B had 5 wrong totals and validation flagged 4; Haiku mode A had 22 wrong or missing totals and flagged 20 (16 of those were "no total found"; of the 6 wrong values, 4 were flagged); GLM mode A had 23 and flagged 20 (5 of its 8 wrong values). It also raises false alarms: it flagged 9 of 45 receipts in B whose total was right, because CORD receipts carry discounts, rounding and service charges that the rules only partly model. Examples are listed in `eval/results.md`, for instance a receipt where the model returned a total of 100000 against a true 60500, caught because the line items summed to 155000 against a subtotal of 95000.
- Latency is the median wall-clock time per receipt (OCR plus LLM for mode A). Means are not reported because the runs hit transient provider errors (OpenRouter credit errors, Z.ai overload) that triggered backoff retries.
- Results vary a little between runs and machines: OCR output and LLM replies are not bit-for-bit repeatable, so a re-run of the same receipt can differ from the cached eval.
- 50 receipts is a small sample, so a few points of difference are noise.

### What is scored

CORD annotates menu items, subtotal, tax and total. So the eval scores `total`, `subtotal`, `tax` and line items (`description`, `qty`, `amount`). **Not scored** because CORD has no ground truth for them: `vendor_name`, `vendor_address`, `date`, `invoice_number`, `currency`, `unit_price`, `discount`, `service_charge`. They are still in the schema and extracted. Amounts are compared numerically after normalising CORD's separators (`60.000` and `60,000` both mean 60000). Descriptions are compared exactly and after lower-casing and removing punctuation. A line item counts as correct when its amount is equal and its description is at least 60% similar (difflib ratio). Subtotal and tax are scored only on receipts that have them.

## Adapt it to your documents

- New document type: edit the Pydantic models in `docextract/schema.py`, the field list in the prompt in `docextract/extract.py`, and the rules in `docextract/validate.py`. Purchase orders, delivery notes, forms and bank statements are the same pipeline with a different schema and different checks.
- Export: CSV and JSON are built in. `export.append_to_sheet` appends rows to a Google Sheet through a service account (untested here: no real sheet was available). The same hook is the place for an ERP, CRM or database insert.
- Sensitive documents: nothing is stored. Point `LLM_PROVIDER` at a model you host (any OpenAI-compatible endpoint) and run the containers on your own infrastructure, including EU or on-premise hosting.

## Run it

```bash
bash scripts/download_data.sh      # CORD (only needed for the eval)
cp .env.example .env               # add ZAI_API_KEY (default, free GLM models) or set LLM_PROVIDER + OPENROUTER/ANTHROPIC/OPENAI key
docker compose up --build          # UI on :8501, API on :8000
```

Open http://localhost:8501 and upload a receipt (or press "Use sample receipt"). API: `curl -F file=@receipt.jpg localhost:8000/extract`.

Without Docker (needs `tesseract-ocr` installed): `python -m venv .venv && .venv/bin/pip install -r requirements.txt`, then `streamlit run ui/app.py` and `uvicorn api.app:app`. Re-run the eval with `python -m eval.run_eval --mode both --tag _glm && python eval/report.py` for the default GLM models, or `LLM_PROVIDER=openrouter python -m eval.run_eval --mode both` for the Haiku columns (replies are cached in `eval/cache`, so an interrupted run resumes).

`docker compose up --build` was tested: both containers started and served the UI, `/health` and `/extract`. The test machine's proxy needed an extra CA certificate during `pip install` inside the build, which is not part of the committed Dockerfile; a normal network does not need it. That test ran before the default switched to Z.ai GLM; the switch only changes environment defaults, and the containers were not rebuilt after it. The demo GIF was also recorded with Haiku via OpenRouter.

## Data and licenses

- **CORD v2** (naver-clova-ix/cord-v2 on Hugging Face), CC-BY-4.0, by Naver CLOVA. Used for the eval and downloaded by `scripts/download_data.sh`; the dataset is not in this repo. `assets/sample_receipt.png` is one CORD test image, included under CC-BY-4.0 with this attribution.
- **SROIE** was left out: its license terms could not be confirmed as permitting this use, so only CORD is used.
- Code: MIT, see `LICENSE`. Dependencies are permissively licensed (Tesseract Apache-2.0, pypdfium2 Apache-2.0/BSD-3, Pydantic, FastAPI, Streamlit, OpenCV, Pillow and the others MIT/BSD/Apache) and are used as installed from PyPI/apt.

Need your documents automated? Hire me on Upwork: https://www.upwork.com/freelancers/~014d8e815fea10ea82
