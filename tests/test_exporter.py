"""
Unit tests for ItemExporter.
"""
import json
import os
import sqlite3
import tempfile
from avito_parser.exporter import ItemExporter
from avito_parser.models import AvitoItem, SellerInfo


def test_exporter_json_and_sqlite():
    item = AvitoItem(
        id="12345",
        title="Test Laptop",
        url="https://www.avito.ru/item_12345",
        price=35000,
        formatted_price="35 000 ₽",
        city="Москва",
        address="Москва, Тверская",
        seller=SellerInfo(name="Продавец", rating=4.9, reviews_count=12),
        params={"Процессор": "Core i5"},
        description="Отличный ноутбук",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "test.json")
        csv_path = os.path.join(tmpdir, "test.csv")
        db_path = os.path.join(tmpdir, "test.db")

        ItemExporter.to_json([item], json_path)
        assert os.path.exists(json_path)
        with open(json_path) as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["price"] == 35000

        ItemExporter.to_csv([item], csv_path)
        assert os.path.exists(csv_path)

        ItemExporter.to_sqlite([item], db_path)
        assert os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT id, title, price, city FROM avito_items").fetchone()
        assert row == ("12345", "Test Laptop", 35000, "Москва")
        conn.close()
