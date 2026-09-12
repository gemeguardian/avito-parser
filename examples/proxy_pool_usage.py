"""
Example 4: Using a pool of proxies with automatic rotation and failover.
"""
from avito_parser import AvitoParser, ProxyManager

PROXIES = [
    # Add your proxies here (HTTP, SOCKS5, or with auth):
    # "socks5h://user:password@proxy1.example.com:2002",
    # "http://proxy2.example.com:8080",
]

def main():
    if not PROXIES:
        print("Please configure PROXIES list first.")
        return

    # Initialize manager with max 2 retries per proxy before deactivation
    proxy_manager = ProxyManager(PROXIES, max_fails=2, randomize=True)

    parser = AvitoParser(
        proxies=proxy_manager,
        min_delay=1.5,
        max_delay=3.5,
        max_retries=3
    )

    url = "https://www.avito.ru/nizhniy_novgorod/noutbuki/honor_magicbook_14_nmh-wfq9hn_16512gb_8388969237"
    item = parser.get_item(url)
    if item:
        print(f"Scraped via proxy pool: {item.title} ({item.formatted_price})")
    else:
        print("Failed to scrape item.")

if __name__ == "__main__":
    main()
