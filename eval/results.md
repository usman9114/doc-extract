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

- Mode A: 22 documents had a wrong total; validation flagged 20 of them. It also flagged 14 of 28 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 4: `total:required; line_items:required; document:ocr_conf`
  - doc 5: `total:required; line_items:required`
  - doc 11: `total:required; line_items:required; document:ocr_conf`
- Mode B: 5 documents had a wrong total; validation flagged 4 of them. It also flagged 9 of 45 documents whose total was right (false alarms: CORD receipts often carry discounts or service charges the rules do not model).
  - doc 13: `total:sum`
  - doc 20: `total:sum`
  - doc 58: `subtotal:items_sum`
