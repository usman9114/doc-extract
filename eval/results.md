# Evaluation results

Dataset: CORD v2 (CC-BY-4.0), the same 50 receipts from the test split for every run (seed 42, `eval/cord.py`), never used for prompt or threshold tuning. Haiku columns: `anthropic/claude-haiku-4.5` via OpenRouter, cost as reported by OpenRouter per call. GLM columns: Z.ai API, `glm-4.5-flash` (text, thinking disabled) and `glm-4.6v-flash` (image); both are free Flash models (https://docs.z.ai/guides/overview/pricing), so cost is $0 while token counts are still recorded. GLM latency includes waiting out the free tier's 'service overloaded' (HTTP 429, code 1305) retries. The GLM image run (`glm-4.6v-flash`) is not in this table: during the run window (about an hour of retries) every request to it returned 'service overloaded' (code 1305), so it could not be measured. Re-run with `LLM_PROVIDER=zai python -m eval.run_eval --mode both --tag _glm`; finished items are cached.

| Metric | A: GLM-4.5-Flash (OCR text) | A: Haiku 4.5 (OCR text) | B: Haiku 4.5 (image) |
|---|---|---|---|
| Total amount correct | 53% | 55% | 90% |
| Subtotal correct (n=33) | 42% | 48% | 85% |
| Tax correct (n=23) | 39% | 39% | 74% |
| Line items: precision | 46% | 52% | 80% |
| Line items: recall | 36% | 38% | 87% |
| Line items: F1 | 41% | 44% | 83% |
| Item description, exact match (of matched items) | 54% | 62% | 77% |
| Item description, normalised match (of matched items) | 54% | 62% | 80% |
| Item quantity correct (of matched items with a quantity) | 76% | 70% | 96% |
| Documents with total/subtotal/tax all correct | 46% | 50% | 76% |
| Documents with every scored field + all line items correct | 14% | 20% | 60% |
| Flagged for review | 66% | 68% | 26% |
| Auto-approved | 34% | 32% | 74% |
| Auto-approved docs with key fields all correct | 76% | 88% | 95% |
| Auto-approved docs with everything correct | 29% | 56% | 78% |
| Median latency per document (s) | 9.3 | 2.6 | 2.9 |
| Mean tokens in / out per document | 476 / 162 | 527 / 189 | 1202 / 236 |
| Cost per 100 documents (US$) | 0.00 | 0.15 | 0.24 |
| Wrong totals / caught by validation | 23 / 20 | 22 / 20 | 5 / 4 |
| Total spend for this run (US$) | 0.000 | 0.074 | 0.119 |

## Validation catching wrong totals

- A: GLM-4.5-Flash (OCR text): 23 documents had a wrong total (15 with no total extracted at all, 8 with a wrong value). Validation flagged 20 of the 23, including 5 of the 8 wrong values. It also flagged 13 of 27 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 13: extracted total 3000, ground truth 51300, flagged by `document:ocr_conf`
  - doc 22: extracted total 49000, ground truth 40000, flagged by `total:sum`
  - doc 29: extracted total 10393, ground truth 145900, flagged by `total:sum`
  - doc 93: extracted total 15777, ground truth 17999, flagged by `subtotal:items_sum; line_items[1]:qty_x_price`
  - missed: doc 5: extracted total 28.182, ground truth 31000, not flagged
  - missed: doc 35: extracted total 36000, ground truth 54000, not flagged
- A: Haiku 4.5 (OCR text): 22 documents had a wrong total (16 with no total extracted at all, 6 with a wrong value). Validation flagged 20 of the 22, including 4 of the 6 wrong values. It also flagged 14 of 28 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 22: extracted total 49000, ground truth 40000, flagged by `subtotal:items_sum`
  - doc 25: extracted total 26000, ground truth 43000, flagged by `document:ocr_conf`
  - doc 29: extracted total 119722, ground truth 145900, flagged by `subtotal:items_sum`
  - doc 71: extracted total 499000, ground truth 198000, flagged by `subtotal:items_sum`
  - missed: doc 35: extracted total 36000, ground truth 54000, not flagged
  - missed: doc 93: extracted total 15777, ground truth 17999, not flagged
- B: Haiku 4.5 (image): 5 documents had a wrong total (0 with no total extracted at all, 5 with a wrong value). Validation flagged 4 of the 5, including 4 of the 5 wrong values. It also flagged 9 of 45 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 13: extracted total 52, ground truth 51300, flagged by `total:sum`
  - doc 20: extracted total 377291, ground truth 377859, flagged by `total:sum`
  - doc 58: extracted total 100000, ground truth 60500, flagged by `subtotal:items_sum`
  - doc 71: extracted total 220000, ground truth 198000, flagged by `total:sum`
  - missed: doc 95: extracted total 62000, ground truth 61799, not flagged
