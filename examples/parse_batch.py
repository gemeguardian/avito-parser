"""
Example 2: Batch parsing multiple items with JSON and CSV export.
"""
from avito_parser import AvitoParser, ItemExporter

URLS = [
    "https://www.avito.ru/nizhniy_novgorod/noutbuki/huawei_matebook_d_15_bod-wfh9_16512_i5-1135g7_8244308650",
    "https://www.avito.ru/nizhniy_novgorod/noutbuki/honor_magicbook_14_nmh-wfq9hn_16512gb_8388969237",
    "https://www.avito.ru/nizhniy_novgorod/noutbuki/dell_15.6_ips_16gbssd512_i5-1145g7_podsvetka_8273384158",
]

def on_item_scraped(item, current, total):
    print(f"[{current}/{total}] {item.title[:40]} -> {item.formatted_price}")

def main():
    with AvitoParser(min_delay=2.5, max_delay=4.5) as parser:
        items = parser.get_items(URLS, callback=on_item_scraped)

        # Print summary table
        ItemExporter.print_summary(items)

        # Export to formats
        ItemExporter.to_json(items, "laptops.json")
        ItemExporter.to_csv(items, "laptops.csv")
        ItemExporter.to_sqlite(items, "laptops.db")
        print("Exported to laptops.json, laptops.csv, and laptops.db!")

if __name__ == "__main__":
    main()
