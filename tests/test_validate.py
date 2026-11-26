from docextract.schema import Document, LineItem
from docextract.validate import validate
from eval.cord import parse_amount


def doc(**kw):
    return Document(line_items=[LineItem(description="a", amount=10), LineItem(description="b", amount=20)], **kw)


def test_ok():
    v = validate(doc(subtotal=30, tax=3, total=33))
    assert not v.needs_review


def test_wrong_total_is_flagged():
    v = validate(doc(subtotal=30, tax=3, total=330))
    assert v.needs_review and "total" in v.bad_fields


def test_items_vs_subtotal():
    assert "subtotal" in validate(doc(subtotal=35, total=35)).bad_fields


def test_bad_date_and_currency():
    v = validate(doc(subtotal=30, total=30, date="2024-13-40", currency="XXX"))
    assert {"date", "currency"} <= v.bad_fields


def test_parse_amount():
    assert parse_amount("60.000") == 60000 and parse_amount("Rp. 5.455") == 5455
    assert parse_amount("12.50") == 12.5 and parse_amount("11,000") == 11000


def test_null_description_is_accepted():
    assert LineItem.model_validate({"description": None, "amount": 5}).description == ""
