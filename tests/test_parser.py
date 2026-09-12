"""
Unit tests for AvitoItemParser and AvitoCatalogParser with real HTML snapshots.
"""
import os
import pytest
from avito_parser.parser import AvitoItemParser, clean_html


def test_clean_html():
    raw = "<p>Hello&nbsp;World!<br />Line 2</p>&#39;test&#39;"
    cleaned = clean_html(raw)
    assert "Hello World!" in cleaned
    assert "Line 2" in cleaned
    assert "'test'" in cleaned
    assert "<p>" not in cleaned


def test_parse_real_avito_html_files():
    # If fixtures exist in /tmp, verify all of them
    found_any = False
    for i in range(1, 8):
        path = f"/tmp/avito_{i}.html"
        if os.path.exists(path):
            found_any = True
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()

            item = AvitoItemParser.parse(html, url=f"https://www.avito.ru/item_{i}")
            assert item is not None
            assert item.title
            assert item.price is not None
            assert item.price > 0
            assert "RUB" in item.currency or "₽" in item.formatted_price
            assert len(item.description) > 0

    if not found_any:
        pytest.skip("Test fixtures /tmp/avito_*.html not present")


def test_parse_honor_magicbook():
    path = "/tmp/avito_7.html"
    if not os.path.exists(path):
        pytest.skip("Fixture /tmp/avito_7.html not present")

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    item = AvitoItemParser.parse(html)
    assert item is not None
    assert "Honor" in item.title or "MagicBook" in item.title
    assert item.price == 32700
    assert "Ryzen 5 5500U" in item.params.get("Процессор", "")
    assert item.params.get("Оперативная память, ГБ") == "16"
    assert item.params.get("Объем накопителей, ГБ") == "512"
    assert "ПРОСТОР" in item.seller.name
