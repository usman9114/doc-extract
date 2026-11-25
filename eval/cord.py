"""CORD v2 loading, ground-truth parsing and scoring helpers."""
from __future__ import annotations

import io
import json
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SEED, N_TEST = 42, 50


def load_split(split: str) -> pd.DataFrame:
    return pd.read_parquet(ROOT / "data" / "cord" / f"{split}.parquet")


def test_ids() -> list[int]:
    """Fixed, seeded held-out subset of the CORD test split (never used for prompt tuning)."""
    return sorted(random.Random(SEED).sample(range(100), N_TEST))


def get_image(df: pd.DataFrame, i: int) -> Image.Image:
    return Image.open(io.BytesIO(df.iloc[i]["image"]["bytes"])).convert("RGB")


def parse_amount(s) -> float | None:
    """'60.000' -> 60000, '11,000' -> 11000, 'Rp. 5.455' -> 5455, '12.50' -> 12.5."""
    if s is None:
        return None
    s = re.sub(r"[^\d.,\-]", "", str(s))
    if not re.search(r"\d", s):
        return None
    neg = s.startswith("-")
    s = s.lstrip("-").strip(".,")
    m = re.search(r"[.,](\d{1,2})$", s)
    if m and not re.search(r"[.,]\d{3}$", s):
        whole, frac = re.sub(r"[.,]", "", s[: m.start()]), m.group(1)
        v = float(f"{whole or 0}.{frac}")
    else:
        v = float(re.sub(r"[.,]", "", s))
    return -v if neg else v


def parse_qty(s) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", str(s or ""))
    return float(m.group().replace(",", ".")) if m else None


def gt_fields(ground_truth: str) -> dict:
    """Map the CORD annotation to our schema; only fields CORD actually annotates."""
    p = json.loads(ground_truth)["gt_parse"]
    menu = p.get("menu", [])
    menu = [menu] if isinstance(menu, dict) else menu
    items = []
    for m in menu:
        if not isinstance(m, dict):
            continue
        for part in (m, m.get("sub") if isinstance(m.get("sub"), dict) else None):
            if part and part.get("nm") and parse_amount(part.get("price")) is not None:
                items.append({"description": part["nm"], "qty": parse_qty(part.get("cnt")),
                              "amount": parse_amount(part["price"])})
    st, tt = p.get("sub_total", {}), p.get("total", {})
    return {
        "subtotal": parse_amount(st.get("subtotal_price")) if isinstance(st, dict) else None,
        "tax": parse_amount(st.get("tax_price")) if isinstance(st, dict) else None,
        "total": parse_amount(tt.get("total_price")) if isinstance(tt, dict) else None,
        "line_items": items,
    }


def norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def match_items(pred: list[dict], gt: list[dict], thr: float = 0.6):
    """Greedy match on equal amount + description similarity. Returns list of (pred, gt) pairs."""
    used, pairs = set(), []
    for g in gt:
        best, bs = None, 0.0
        for k, p in enumerate(pred):
            if k in used or p["amount"] is None or abs(p["amount"] - g["amount"]) > 0.5:
                continue
            s = sim(p["description"], g["description"])
            if s > bs:
                best, bs = k, s
        if best is not None and bs >= thr:
            used.add(best)
            pairs.append((pred[best], g))
    return pairs
