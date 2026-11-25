"""Build eval/results.md and assets/accuracy_chart.png from summary.json + results.csv."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parent
S = {s["mode"]: s for s in json.loads((HERE / "summary.json").read_text())}
R = pd.read_csv(HERE / "results.csv")
MODEL = "anthropic/claude-haiku-4.5 via OpenRouter"
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
A, B = S["text"], S["vision"]
md = [f"# Evaluation results\n\nModel: `{MODEL}`. Dataset: CORD v2 (CC-BY-4.0), {A['docs']} receipts from the test split "
      "(seed 42, `eval/cord.py`), never used for prompt or threshold tuning. Costs are the amounts OpenRouter "
      "reported per call.\n",
      "| Metric | A: OCR text to LLM | B: image to vision LLM |", "|---|---|---|"]
for label, key, f in rows:
    if key is None:
        md.append(f"| {label} | {A['tokens_in_mean']:.0f} / {A['tokens_out_mean']:.0f} | {B['tokens_in_mean']:.0f} / {B['tokens_out_mean']:.0f} |")
    else:
        md.append(f"| {label.format(**A)} | {f(A[key])} | {f(B[key])} |")
md.append(f"| Wrong totals / caught by validation | {A['wrong_total_docs']} / {A['wrong_total_caught']} | "
          f"{B['wrong_total_docs']} / {B['wrong_total_caught']} |")
md.append(f"| Total spend for this run (US$) | {A['cost_total']:.3f} | {B['cost_total']:.3f} |")

md.append("\n## Validation catching wrong totals\n")
for mode, name in (("text", "A"), ("vision", "B")):
    r = R[(R["mode"] == mode)]
    wt = r[r.wrong_total == True]  # noqa: E712
    cor = r[r.wrong_total == False]  # noqa: E712
    md.append(f"- Mode {name}: {len(wt)} documents had a wrong total; validation flagged {int(wt.flagged.sum())} of them. "
              f"It also flagged {int(cor.flagged.sum())} of {len(cor)} documents whose total was right "
              "(false alarms: CORD receipts often carry discounts or service charges the rules do not model).")
    for _, x in wt[wt.flagged].head(3).iterrows():
        md.append(f"  - doc {int(x.doc)}: `{x.reasons}`")
(HERE / "results.md").write_text("\n".join(md) + "\n")
print("\n".join(md))

# chart
labels = ["Total", "Subtotal", "Tax", "Line items F1", "Item qty", "All key fields\n(doc level)", "Everything\n(doc level)"]
keys = ["total_acc", "subtotal_acc", "tax_acc", "item_f1", "qty_acc", "doc_key_fields_ok", "doc_all_ok"]
fig, ax = plt.subplots(figsize=(11, 5.2), dpi=150)
fig.patch.set_facecolor("#0f1115"); ax.set_facecolor("#0f1115")
x = range(len(keys)); w = 0.38
b1 = ax.bar([i - w / 2 for i in x], [100 * A[k] for k in keys], w, color="#7f8c9a", label="A: OCR text to LLM")
b2 = ax.bar([i + w / 2 for i in x], [100 * B[k] for k in keys], w, color="#3ddc97", label="B: image to vision LLM")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.0f}", ha="center", color="white", fontsize=9)
ax.set_xticks(list(x)); ax.set_xticklabels(labels, color="white", fontsize=9)
ax.set_ylim(0, 112); ax.set_ylabel("accuracy, %", color="white"); ax.tick_params(colors="white")
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#555")
ax.set_title(f"Field accuracy on {A['docs']} held-out CORD receipts", color="white", loc="left")
ax.legend(facecolor="#0f1115", labelcolor="white", edgecolor="#555", loc="lower left")
fig.tight_layout(); fig.savefig(ROOT / "assets" / "accuracy_chart.png")
