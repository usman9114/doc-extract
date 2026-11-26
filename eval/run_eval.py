"""Field-level evaluation on the held-out CORD subset. Resumable: every LLM reply is cached on disk.

usage: python -m eval.run_eval --mode text|vision|both [--split test|validation --limit N] [--tag NAME]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docextract import llm  # noqa: E402
from docextract.extract import SYSTEM, extract  # noqa: E402
from docextract.ocr import run_ocr  # noqa: E402
from docextract.preprocess import downscale_jpeg, preprocess  # noqa: E402
from docextract.schema import Result  # noqa: E402
from eval import cord  # noqa: E402

CACHE = cord.ROOT / "eval" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)


def run_doc(df, i: int, mode: str, split: str) -> dict:
    """Run one document through the pipeline (cached). Returns Result json + ocr_words."""
    model = llm.model_name(vision=mode == "vision").replace("/", "_")
    sig = hashlib.md5(SYSTEM.encode()).hexdigest()[:6]
    f = CACHE / f"{split}_{i}_{mode}_{model}_{sig}.json"
    if f.exists():
        return json.loads(f.read_text())
    img = cord.get_image(df, i)
    t0 = time.time()
    img = preprocess(img)
    if mode == "text":
        ocr = run_ocr(img)
        res = extract("text", ocr_text=ocr.text, ocr_conf=ocr.mean_conf)
        res.latency_s += time.time() - t0 - res.latency_s  # OCR + LLM wall time
    else:
        res = extract("vision", image_jpeg=downscale_jpeg(img))
    out = res.model_dump()
    f.write_text(json.dumps(out))
    return out


def score_doc(res: dict, gt: dict) -> dict:
    d = res["document"]
    row = {"flagged": res["validation"]["needs_review"],
           "reasons": "; ".join(f'{x["field"]}:{x["rule"]}' for x in res["validation"]["issues"])}
    row["pred_total"], row["gt_total"] = d["total"], gt["total"]
    key_ok = []
    for k in ("total", "subtotal", "tax"):
        if gt[k] is None:
            row[k] = None
            continue
        ok = d[k] is not None and abs(d[k] - gt[k]) < 0.5
        row[k] = ok
        key_ok.append(ok)
    pred = d["line_items"]
    pairs = cord.match_items(pred, gt["line_items"])
    row["items_tp"], row["items_pred"], row["items_gt"] = len(pairs), len(pred), len(gt["line_items"])
    row["desc_exact"] = sum(p["description"].strip().lower() == g["description"].strip().lower() for p, g in pairs)
    row["desc_norm"] = sum(cord.norm_text(p["description"]) == cord.norm_text(g["description"]) for p, g in pairs)
    qg = [(p, g) for p, g in pairs if g["qty"] is not None]
    row["qty_n"], row["qty_ok"] = len(qg), sum(p["qty"] is not None and abs(p["qty"] - g["qty"]) < 0.01 for p, g in qg)
    row["items_ok"] = len(pairs) == row["items_gt"] == row["items_pred"]
    row["all_key_ok"] = all(key_ok)
    row["all_ok"] = row["all_key_ok"] and row["items_ok"]
    row["wrong_total"] = gt["total"] is not None and not row["total"]
    for k in ("prompt_tokens", "completion_tokens", "cost_usd", "latency_s", "attempts"):
        row[k] = res[k]
    return row


def summarise(rows: pd.DataFrame, mode: str) -> dict:
    def acc(col):
        s = rows[col].dropna()
        return (s.astype(bool).mean(), len(s))

    ti, tp, tg = rows.items_tp.sum(), rows.items_pred.sum(), rows.items_gt.sum()
    prec, rec = ti / max(tp, 1), ti / max(tg, 1)
    wt = rows[rows.wrong_total]
    auto = rows[~rows.flagged]
    return {
        "mode": mode, "docs": len(rows),
        "total_acc": acc("total")[0], "subtotal_acc": acc("subtotal")[0], "tax_acc": acc("tax")[0],
        "n_subtotal": acc("subtotal")[1], "n_tax": acc("tax")[1],
        "item_precision": prec, "item_recall": rec, "item_f1": 2 * prec * rec / max(prec + rec, 1e-9),
        "desc_exact": rows.desc_exact.sum() / max(ti, 1), "desc_norm": rows.desc_norm.sum() / max(ti, 1),
        "qty_acc": rows.qty_ok.sum() / max(rows.qty_n.sum(), 1),
        "doc_key_fields_ok": rows.all_key_ok.mean(), "doc_all_ok": rows.all_ok.mean(),
        "flagged_pct": rows.flagged.mean(),
        "wrong_total_docs": len(wt), "wrong_total_caught": int(wt.flagged.sum()),
        "auto_approved_pct": 1 - rows.flagged.mean(),
        "auto_approved_key_ok": auto.all_key_ok.mean() if len(auto) else float("nan"),
        "auto_approved_all_ok": auto.all_ok.mean() if len(auto) else float("nan"),
        "latency_s_mean": rows.latency_s.mean(), "latency_s_p50": rows.latency_s.median(),
        "cost_per_100": rows.cost_usd.sum() / len(rows) * 100, "cost_total": rows.cost_usd.sum(),
        "tokens_in_mean": rows.prompt_tokens.mean(), "tokens_out_mean": rows.completion_tokens.mean(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="both")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    df = cord.load_split(a.split)
    ids = cord.test_ids() if a.split == "test" else list(range(len(df)))
    if a.limit:
        ids = ids[: a.limit]
    modes = ["text", "vision"] if a.mode == "both" else [a.mode]
    from concurrent.futures import ThreadPoolExecutor

    summaries, all_rows = [], []
    for mode in modes:
        def job(i):
            res = run_doc(df, i, mode, a.split)
            return {"doc": i, "mode": mode, **score_doc(res, cord.gt_fields(df.iloc[i]["ground_truth"])),
                    "_res": res}
        with ThreadPoolExecutor(a.workers) as ex:
            rows = list(ex.map(job, ids))
        pd_rows = pd.DataFrame([{k: v for k, v in r.items() if k != "_res"} for r in rows])
        all_rows.append(pd_rows)
        summaries.append(summarise(pd_rows, mode))
        print(json.dumps(summaries[-1], indent=1, default=float))
    if a.split == "test" and not a.limit:
        out = Path(__file__).parent
        (out / f"results{a.tag}.csv").write_text(pd.concat(all_rows).to_csv(index=False))
        (out / f"summary{a.tag}.json").write_text(json.dumps(summaries, indent=1, default=float))
        print("wrote results/summary", a.tag)


if __name__ == "__main__":
    main()
