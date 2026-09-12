"""
Export utilities for scraped Avito items (JSON, CSV, SQLite, Pretty Table).
"""
import csv
import json
import sqlite3
from typing import List, Optional
from .models import AvitoItem


class ItemExporter:
    """
    Exports a collection of AvitoItem models into various formats.
    """

    @staticmethod
    def to_json(items: List[AvitoItem], filepath: str, indent: int = 2):
        """Save items to a JSON file."""
        data = [it.to_dict() for it in items]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

    @staticmethod
    def to_jsonl(items: List[AvitoItem], filepath: str):
        """Save items to a JSON Lines file."""
        with open(filepath, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")

    @staticmethod
    def to_csv(items: List[AvitoItem], filepath: str):
        """Save items to a CSV file with flattened key parameters."""
        if not items:
            return

        headers = [
            "id",
            "title",
            "price",
            "currency",
            "formatted_price",
            "city",
            "address",
            "seller_name",
            "seller_rating",
            "seller_reviews",
            "url",
            "description",
        ]

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for it in items:
                writer.writerow([
                    it.id,
                    it.title,
                    it.price,
                    it.currency,
                    it.formatted_price,
                    it.city,
                    it.address,
                    it.seller.name,
                    it.seller.rating or "",
                    it.seller.reviews_count or "",
                    it.url,
                    it.description.replace("\n", " ")[:500],
                ])

    @staticmethod
    def to_sqlite(items: List[AvitoItem], db_path: str, table_name: str = "avito_items"):
        """Save or update items in an SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id TEXT PRIMARY KEY,
                title TEXT,
                price INTEGER,
                currency TEXT,
                formatted_price TEXT,
                city TEXT,
                address TEXT,
                seller_name TEXT,
                seller_rating REAL,
                seller_reviews INTEGER,
                params_json TEXT,
                description TEXT,
                url TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for it in items:
            cursor.execute(f"""
                INSERT OR REPLACE INTO {table_name} (
                    id, title, price, currency, formatted_price, city, address,
                    seller_name, seller_rating, seller_reviews, params_json, description, url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                it.id,
                it.title,
                it.price,
                it.currency,
                it.formatted_price,
                it.city,
                it.address,
                it.seller.name,
                it.seller.rating,
                it.seller.reviews_count,
                json.dumps(it.params, ensure_ascii=False),
                it.description,
                it.url,
            ))

        conn.commit()
        conn.close()

    @staticmethod
    def print_summary(items: List[AvitoItem]):
        """Print a clean ASCII summary table to stdout."""
        print("\n" + "=" * 90)
        print(f"{'#':<3} | {'Название':<35} | {'Цена':<14} | {'Город':<15} | {'Продавец'}")
        print("-" * 90)
        for i, it in enumerate(items, 1):
            title_trunc = it.title[:33] + ".." if len(it.title) > 35 else it.title
            price_str = it.formatted_price or "N/A"
            city_str = it.city[:14] if it.city else "-"
            seller_str = it.seller.name[:18] if it.seller.name else "-"
            print(f"{i:<3} | {title_trunc:<35} | {price_str:<14} | {city_str:<15} | {seller_str}")
        print("=" * 90 + "\n")
