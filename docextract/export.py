"""JSON / CSV export and optional Google Sheets append."""
from __future__ import annotations

import csv
import io
import json
import os

from .schema import Result

HEADER = ["vendor_name", "date", "invoice_number", "currency", "subtotal", "tax", "total",
          "line_no", "description", "qty", "unit_price", "amount", "needs_review", "review_reasons"]


def to_json(r: Result) -> str:
    return r.model_dump_json(indent=2)


def rows(r: Result) -> list[list]:
    d, v = r.document, r.validation
    head = [d.vendor_name, d.date, d.invoice_number, d.currency, d.subtotal, d.tax, d.total]
    tail = [v.needs_review, "; ".join(i.message for i in v.issues)]
    items = d.line_items or [None]
    return [head + ([n, i.description, i.qty, i.unit_price, i.amount] if i else [None] * 5) + tail
            for n, i in enumerate(items, 1)]


def to_csv(r: Result) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    w.writerows(rows(r))
    return buf.getvalue()


def append_to_sheet(r: Result, sheet_id: str | None = None, creds_json: str | None = None) -> int:
    """Append one row per line item to the first worksheet. Needs `pip install gspread`
    and a service account shared on the sheet. Not exercised in the eval."""
    import gspread

    gc = gspread.service_account(filename=creds_json or os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    ws = gc.open_by_key(sheet_id or os.environ["GOOGLE_SHEET_ID"]).sheet1
    data = rows(r)
    ws.append_rows(data, value_input_option="USER_ENTERED")
    return len(data)
