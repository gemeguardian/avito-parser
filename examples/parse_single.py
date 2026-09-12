"""
Example 1: Parsing a single Avito item by URL.
"""
from avito_parser import AvitoParser

def main():
    # Initialize parser
    # Pass proxy if scraping from outside Russia or from datacenter IPs:
    # parser = AvitoParser(proxies="socks5h://user:pass@host:port")
    parser = AvitoParser(min_delay=2.0, max_delay=4.0)

    url = "https://www.avito.ru/nizhniy_novgorod/noutbuki/honor_magicbook_14_nmh-wfq9hn_16512gb_8388969237"
    print(f"Fetching {url}...")

    item = parser.get_item(url)
    if item:
        print("\n=== ITEM DETAILS ===")
        print(f"Title   : {item.title}")
        print(f"Price   : {item.formatted_price}")
        print(f"City    : {item.city}")
        print(f"Address : {item.address}")
        print(f"Seller  : {item.seller.name} (★ {item.seller.rating})")
        print("\nSpecifications:")
        for k, v in item.params.items():
            print(f"  • {k}: {v}")
        print(f"\nDescription:\n{item.description[:300]}...\n")
    else:
        print("Failed to fetch item.")

if __name__ == "__main__":
    main()
