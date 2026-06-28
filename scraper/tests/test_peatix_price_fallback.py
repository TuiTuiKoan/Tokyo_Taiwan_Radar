import pytest

from sources.peatix import (
    _derive_is_paid,
    _extract_price_amount,
    _extract_price_from_text,
    _is_generic_price_text,
)


@pytest.mark.parametrize(
    ("text", "expected_price", "expected_amount", "expected_paid"),
    [
        ("参加費｜800円(税込)", "800円(税込)", 800, True),
        ("料金：無料", "無料", None, False),
        ("費用 ¥1,500", "¥1,500", 1500, True),
        ("入場：会員 免費 / 一般 1,000円", "会員 免費 / 一般 1,000円", 1000, True),
        ("チケット 大人 前売券1,000円 当日券1,200円", "大人 前売券1,000円 当日券1,200円", None, True),
        ("参加費：800~1000円", "800~1000円", None, True),
    ],
)
def test_extract_price_from_labeled_body_text(text, expected_price, expected_amount, expected_paid):
    price = _extract_price_from_text(text)

    assert price == expected_price
    assert _extract_price_amount(price) == expected_amount
    assert _derive_is_paid(price) is expected_paid


def test_extract_price_ignores_unlabeled_amounts():
    assert _extract_price_from_text("台湾茶を800円相当のお土産として配布します") is None


@pytest.mark.parametrize("text", ["料金", "チケット", "参加費：", "  入場料｜ "])
def test_generic_price_text(text):
    assert _is_generic_price_text(text) is True
