"""
Unit tests for AvitoItemParser and AvitoCatalogParser with real HTML snapshots.
"""
import os
import pytest
from avito_parser.parser import AvitoCatalogParser, AvitoItemParser, clean_html


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


def test_parse_m_mobile_catalog():
    # Simulates m.avito.ru HTML where __staticRouterHydrationData has item-list: null
    mock_m_html = """
    <html>
    <head><title>Купить ноутбук в Нижнем Новгороде | Авито</title></head>
    <body>
    <span class="page-title-count-xyz">1 245 объявлений</span>
    <div data-marker="item">
        <a data-marker="item/link" href="/nizhniy_novgorod/noutbuki/dell_latitude_5520_16gb_4111222333?context=H4sIAAAAA">
            <h3 data-marker="titleLabelGrid">Ноутбук Dell &quot;Latitude&quot; 5520 i5 16Gb</h3>
        </a>
        <span data-marker="priceLabelGrid">29&nbsp;990&nbsp;₽</span>
        <div data-marker="sellerAndRatingSellerLabel">ТехноМаркет</div>
        <span data-marker="geoReferenceLeftLabel">р-н Нижегородский</span>
        <span data-marker="geoReferenceRightLabel">ул. Горького</span>
        <span data-marker="sortTimeGrid">10 минут назад</span>
    </div>
    <div data-marker="item">
        <a data-marker="item/link" href="https://m.avito.ru/nizhniy_novgorod/noutbuki/thinkpad_t14_gen2_4222333444?context=XYZ123">
            <h3 data-marker="titleLabelGrid">Lenovo ThinkPad T14 Gen 2</h3>
        </a>
        <span data-marker="priceLabelGrid">31 000 ₽</span>
        <div data-marker="sellerAndRatingSellerLabel">Иван</div>
        <span data-marker="geoReferenceLeftLabel">м. Горьковская</span>
        <span data-marker="sortTimeGrid">1 час назад</span>
    </div>
    </body>
    </html>
    """
    res = AvitoCatalogParser.parse(mock_m_html, url="https://m.avito.ru/nizhniy_novgorod/noutbuki")
    assert len(res.items) == 2
    assert res.total_count == 1245

    item1 = res.items[0]
    assert item1.id == "4111222333"
    assert item1.title == 'Ноутбук Dell "Latitude" 5520 i5 16Gb'
    assert item1.price == 29990
    assert "29 990 ₽" in item1.formatted_price
    assert item1.url == "https://www.avito.ru/nizhniy_novgorod/noutbuki/dell_latitude_5520_16gb_4111222333"
    assert "context" not in item1.url
    assert "р-н Нижегородский" in item1.location
    assert "ул. Горького" in item1.location
    assert item1.time == "10 минут назад"

    item2 = res.items[1]
    assert item2.id == "4222333444"
    assert item2.title == "Lenovo ThinkPad T14 Gen 2"
    assert item2.price == 31000
    assert item2.url == "https://www.avito.ru/nizhniy_novgorod/noutbuki/thinkpad_t14_gen2_4222333444"
    assert "context" not in item2.url
    assert "Горьковская" in item2.location

