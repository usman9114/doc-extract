"""Build eval/results.md and assets/accuracy_chart.png from the summary/results files of each run.

Runs: "" = claude-haiku-4.5 via OpenRouter (both modes), "_glm" = Z.ai GLM Flash
(glm-4.5-flash for text, glm-4.6v-flash for images).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parent
RUNS = [  # (tag, label per mode)
    ("_glm", {"text": "A: GLM-4.5-Flash (OCR text)", "vision": "B: GLM-4.6V-Flash (image)"}, "Z.ai API, free tier"),
    ("", {"text": "A: Haiku 4.5 (OCR text)", "vision": "B: Haiku 4.5 (image)"}, "OpenRouter"),
]
COLS = []  # (label, summary dict, results frame, via)
for tag, labels, via in RUNS:
    if not (HERE / f"summary{tag}.json").exists():
        continue
    res = pd.read_csv(HERE / f"results{tag}.csv")
    for s in json.loads((HERE / f"summary{tag}.json").read_text()):
        COLS.append((labels[s["mode"]], s, res[res["mode"] == s["mode"]], via))

pct = lambda x: f"{100 * x:.0f}%"  # noqa: E731
rows = [
    ("Total amount correct", "total_acc", pct),
    ("Subtotal correct (n={n_subtotal})", "subtotal_acc", pct),
    ("Tax correct (n={n_tax})", "tax_acc", pct),
    ("Line items: precision", "item_precision", pct),
    ("Line items: recall", "item_recall", pct),
    ("Line items: F1", "item_f1", pct),
    ("Item description, exact match (of matched items)", "desc_exact", pct),
    ("Item description, normalised match (of matched items)", "desc_norm", pct),
    ("Item quantity correct (of matched items with a quantity)", "qty_acc", pct),
    ("Documents with total/subtotal/tax all correct", "doc_key_fields_ok", pct),
    ("Documents with every scored field + all line items correct", "doc_all_ok", pct),
    ("Flagged for review", "flagged_pct", pct),
    ("Auto-approved", "auto_approved_pct", pct),
    ("Auto-approved docs with key fields all correct", "auto_approved_key_ok", pct),
    ("Auto-approved docs with everything correct", "auto_approved_all_ok", pct),
    ("Median latency per document (s)", "latency_s_p50", lambda x: f"{x:.1f}"),
    ("Mean tokens in / out per document", None, None),
    ("Cost per 100 documents (US$)", "cost_per_100", lambda x: f"{x:.2f}"),
]
n = COLS[0][1]["docs"]
md = [f"# Evaluation results\n\nDataset: CORD v2 (CC-BY-4.0), the same {n} receipts from the test split for every run "
      "(seed 42, `eval/cord.py`), never used for prompt or threshold tuning. "
      "Haiku columns: `anthropic/claude-haiku-4.5` via OpenRouter, cost as reported by OpenRouter per call. "
      "GLM columns: Z.ai API, `glm-4.5-flash` (text, thinking disabled) and `glm-4.6v-flash` (image); "
      "both are free Flash models (https://docs.z.ai/guides/overview/pricing), so cost is $0 while token counts "
      "are still recorded. GLM latency includes waiting out the free tier's 'service overloaded' (HTTP 429, code 1305) "
      "retries." + ("" if any(c[0].startswith("B: GLM") for c in COLS) else
      " The GLM image run (`glm-4.6v-flash`) is not in this table: during the run window (about an hour of retries) "
      "every request to it returned 'service overloaded' (code 1305), so it could not be measured. "
      "Re-run with `LLM_PROVIDER=zai python -m eval.run_eval --mode both --tag _glm`; finished items are cached.") + "\n",
      "| Metric | " + " | ".join(c[0] for c in COLS) + " |", "|---" * (len(COLS) + 1) + "|"]
for label, key, f in rows:
    if key is None:
        md.append(f"| {label} | " + " | ".join(f"{c[1]['tokens_in_mean']:.0f} / {c[1]['tokens_out_mean']:.0f}" for c in COLS) + " |")
    else:
        md.append(f"| {label.format(**COLS[0][1])} | " + " | ".join(f(c[1][key]) for c in COLS) + " |")
md.append("| Wrong totals / caught by validation | " + " | ".join(
    f"{c[1]['wrong_total_docs']} / {c[1]['wrong_total_caught']}" for c in COLS) + " |")
md.append("| Total spend for this run (US$) | " + " | ".join(f"{c[1]['cost_total']:.3f}" for c in COLS) + " |")

md.append("\n## Validation catching wrong totals\n")
for label, s, r, via in COLS:
    wt = r[r.wrong_total == True]  # noqa: E712
    cor = r[r.wrong_total == False]  # noqa: E712
    empty = wt[wt.pred_total.isna()]
    val = wt[wt.pred_total.notna()]
    md.append(f"- {label}: {len(wt)} documents had a wrong total ({len(empty)} with no total extracted at all, "
              f"{len(val)} with a wrong value). Validation flagged {int(wt.flagged.sum())} of the {len(wt)}, "
              f"including {int(val.flagged.sum())} of the {len(val)} wrong values. "
              f"It also flagged {int(cor.flagged.sum())} of {len(cor)} documents whose total was right "
              "(false alarms: CORD receipts often carry discounts or service charges the rules do not model).")
    for _, x in val[val.flagged].head(4).iterrows():
        md.append(f"  - doc {int(x.doc)}: extracted total {x.pred_total:g}, ground truth {x.gt_total:g}, flagged by `{x.reasons}`")
    for _, x in val[~val.flagged].head(2).iterrows():
        md.append(f"  - missed: doc {int(x.doc)}: extracted total {x.pred_total:g}, ground truth {x.gt_total:g}, not flagged")
(HERE / "results.md").write_text("\n".join(md) + "\n")
print("\n".join(md))

# chart
labels = ["Total", "Subtotal", "Tax", "Line items F1", "Item qty", "All key fields\n(doc level)", "Everything\n(doc level)"]
keys = ["total_acc", "subtotal_acc", "tax_acc", "item_f1", "qty_acc", "doc_key_fields_ok", "doc_all_ok"]
colors = {"A: GLM": "#8fb3ff", "B: GLM": "#3a6ff7", "A: Haiku": "#9aa3ad", "B: Haiku": "#3ddc97"}
fig, ax = plt.subplots(figsize=(12, 5.6), dpi=150)
fig.patch.set_facecolor("#0f1115"); ax.set_facecolor("#0f1115")
w = 0.8 / len(COLS)
for j, (label, s, _, _) in enumerate(COLS):
    color = next(v for k, v in colors.items() if label.startswith(k))
    xs = [i - 0.4 + w * (j + 0.5) for i in range(len(keys))]
    bars = ax.bar(xs, [100 * s[k] for k in keys], w, color=color, label=label)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.0f}", ha="center",
                color="white", fontsize=7.5)
ax.set_xticks(range(len(keys))); ax.set_xticklabels(labels, color="white", fontsize=9)
ax.set_ylim(0, 122); ax.set_ylabel("accuracy, %", color="white"); ax.tick_params(colors="white")
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
for sp in ("left", "bottom"): ax.spines[sp].set_color("#555")
ax.set_title(f"Field accuracy on {n} held-out CORD receipts", color="white", loc="left")
ax.legend(facecolor="#0f1115", labelcolor="white", edgecolor="#555", loc="upper center", ncol=len(COLS),
          bbox_to_anchor=(0.5, 1.0), fontsize=8.5)
fig.tight_layout(); fig.savefig(ROOT / "assets" / "accuracy_chart.png")
