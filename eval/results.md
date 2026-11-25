# Evaluation results

Model: `anthropic/claude-haiku-4.5 via OpenRouter`. Dataset: CORD v2 (CC-BY-4.0), 50 receipts from the test split (seed 42, `eval/cord.py`), never used for prompt or threshold tuning. Costs are the amounts OpenRouter reported per call.

| Metric | A: OCR text to LLM | B: image to vision LLM |
|---|---|---|
| Total amount correct | 55% | 90% |
| Subtotal correct (n=33) | 48% | 85% |
| Tax correct (n=23) | 39% | 74% |
| Line items: precision | 52% | 80% |
| Line items: recall | 38% | 87% |
| Line items: F1 | 44% | 83% |
| Item description, exact match (of matched items) | 62% | 77% |
| Item description, normalised match (of matched items) | 62% | 80% |
| Item quantity correct (of matched items with a quantity) | 70% | 96% |
| Documents with total/subtotal/tax all correct | 50% | 76% |
| Documents with every scored field + all line items correct | 20% | 60% |
| Flagged for review | 68% | 26% |
| Auto-approved | 32% | 74% |
| Auto-approved docs with key fields all correct | 88% | 95% |
| Auto-approved docs with everything correct | 56% | 78% |
| Median latency per document (s) | 2.6 | 2.9 |
| Mean tokens in / out per document | 527 / 189 | 1202 / 236 |
| Cost per 100 documents (US$) | 0.15 | 0.24 |
| Wrong totals / caught by validation | 22 / 20 | 5 / 4 |
| Total spend for this run (US$) | 0.074 | 0.119 |

## Validation catching wrong totals

- Mode A: 22 documents had a wrong total (16 with no total extracted at all, 6 with a wrong value). Validation flagged 20 of the 22, including 4 of the 6 wrong values. It also flagged 14 of 28 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 22: extracted total 49000, ground truth 40000, flagged by `subtotal:items_sum`
  - doc 25: extracted total 26000, ground truth 43000, flagged by `document:ocr_conf`
  - doc 29: extracted total 119722, ground truth 145900, flagged by `subtotal:items_sum`
  - doc 71: extracted total 499000, ground truth 198000, flagged by `subtotal:items_sum`
  - missed: doc 35: extracted total 36000, ground truth 54000, not flagged
  - missed: doc 93: extracted total 15777, ground truth 17999, not flagged
- Mode B: 5 documents had a wrong total (0 with no total extracted at all, 5 with a wrong value). Validation flagged 4 of the 5, including 4 of the 5 wrong values. It also flagged 9 of 45 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 13: extracted total 52, ground truth 51300, flagged by `total:sum`
  - doc 20: extracted total 377291, ground truth 377859, flagged by `total:sum`
  - doc 58: extracted total 100000, ground truth 60500, flagged by `subtotal:items_sum`
  - doc 71: extracted total 220000, ground truth 198000, flagged by `total:sum`
  - missed: doc 95: extracted total 62000, ground truth 61799, not flagged
