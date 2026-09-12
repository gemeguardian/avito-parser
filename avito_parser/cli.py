"""
Command-line interface (CLI) for avito-parser.
"""
import argparse
import logging
import sys
from typing import List

from .client import AvitoParser
from .exporter import ItemExporter
from .models import AvitoItem
from .pow import AvitoPoWSolver


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


def cmd_item(args):
    setup_logging(args.verbose)
    parser = AvitoParser(
        proxies=args.proxy,
        profile=args.profile,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    items: List[AvitoItem] = []
    print(f"[*] Fetching {len(args.urls)} item(s) using profile '{args.profile or 'balanced'}'...")

    def progress(item: AvitoItem, current: int, total: int):
        print(f"[{current}/{total}] Found: {item.title} — {item.formatted_price}")

    items = parser.get_items(args.urls, callback=progress)

    ItemExporter.print_summary(items)
    metrics = parser.get_metrics()
    print(f"[i] Metrics: {metrics['successful_requests']}/{metrics['total_requests']} successful, "
          f"PoW solved: {metrics['pow_challenges_solved']}, rate limits: {metrics['rate_limits_hit']}, "
          f"avg delay: {metrics['average_delay_seconds']}s")

    if args.json:
        ItemExporter.to_json(items, args.json)
        print(f"[+] Saved JSON to {args.json}")
    if args.csv:
        ItemExporter.to_csv(items, args.csv)
        print(f"[+] Saved CSV to {args.csv}")
    if args.sqlite:
        ItemExporter.to_sqlite(items, args.sqlite)
        print(f"[+] Saved SQLite database to {args.sqlite}")


def cmd_batch(args):
    setup_logging(args.verbose)
    with open(args.file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    proxies = None
    if args.proxy_file:
        with open(args.proxy_file, "r", encoding="utf-8") as pf:
            proxies = [line.strip() for line in pf if line.strip()]
    elif args.proxy:
        proxies = args.proxy

    parser = AvitoParser(
        proxies=proxies,
        profile=args.profile,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    print(f"[*] Processing batch of {len(urls)} URLs with profile '{args.profile or 'balanced'}'...")

    def progress(item: AvitoItem, current: int, total: int):
        print(f"[{current}/{total}] {item.title} -> {item.formatted_price}")

    items = parser.get_items(urls, callback=progress)
    ItemExporter.print_summary(items)
    metrics = parser.get_metrics()
    print(f"[i] Metrics: {metrics['successful_requests']}/{metrics['total_requests']} successful, "
          f"PoW solved: {metrics['pow_challenges_solved']}, rate limits: {metrics['rate_limits_hit']}, "
          f"avg delay: {metrics['average_delay_seconds']}s")

    if args.json:
        ItemExporter.to_json(items, args.json)
        print(f"[+] Saved JSON to {args.json}")
    if args.csv:
        ItemExporter.to_csv(items, args.csv)
        print(f"[+] Saved CSV to {args.csv}")
    if args.sqlite:
        ItemExporter.to_sqlite(items, args.sqlite)
        print(f"[+] Saved SQLite database to {args.sqlite}")


def cmd_search(args):
    setup_logging(args.verbose)
    parser = AvitoParser(
        proxies=args.proxy,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    print(f"[*] Searching for '{args.query}' (location={args.location}, page={args.page})...")
    res = parser.search(args.query, location=args.location, page=args.page)
    print(f"\n[+] Total items found: {res.total_count or len(res.items)}")
    print("-" * 75)
    for i, it in enumerate(res.items, 1):
        print(f"{i:<3} | {it.title[:38]:<40} | {it.formatted_price:<12} | {it.url}")
    print("-" * 75)


def cmd_test_pow(args):
    setup_logging(True)
    print("[*] Testing Avito PoW solver directly...")
    parser = AvitoParser(proxies=args.proxy)
    success = parser.warmup()
    if success:
        print("[+] SUCCESS: PoW challenge was solved or session warmed up!")
    else:
        print("[-] FAILED: Could not pass challenge.")


def main():
    parser = argparse.ArgumentParser(
        prog="avito-parser",
        description="Production-ready Avito scraper with automated PoW bypass and proxy rotation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Item subcommand
    p_item = subparsers.add_parser("item", help="Parse one or more item URLs")
    p_item.add_argument("urls", nargs="+", help="Avito item URL(s)")
    p_item.add_argument("--proxy", help="Proxy URL (socks5h://... or http://...)")
    p_item.add_argument("--profile", choices=["stealth", "balanced", "fast_rotating", "datacenter"], default=None, help="Rate limit profile")
    p_item.add_argument("--json", help="Export to JSON file")
    p_item.add_argument("--csv", help="Export to CSV file")
    p_item.add_argument("--sqlite", help="Export to SQLite database")
    p_item.add_argument("--min-delay", type=float, default=None, help="Override min delay (sec)")
    p_item.add_argument("--max-delay", type=float, default=None, help="Override max delay (sec)")
    p_item.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    p_item.set_defaults(func=cmd_item)

    # Batch subcommand
    p_batch = subparsers.add_parser("batch", help="Parse item URLs from a file")
    p_batch.add_argument("file", help="Path to text file containing item URLs")
    p_batch.add_argument("--proxy-file", help="Path to text file with proxy list")
    p_batch.add_argument("--proxy", help="Single proxy URL")
    p_batch.add_argument("--profile", choices=["stealth", "balanced", "fast_rotating", "datacenter"], default=None, help="Rate limit profile")
    p_batch.add_argument("--json", help="Export to JSON file")
    p_batch.add_argument("--csv", help="Export to CSV file")
    p_batch.add_argument("--sqlite", help="Export to SQLite database")
    p_batch.add_argument("--min-delay", type=float, default=None, help="Override min delay")
    p_batch.add_argument("--max-delay", type=float, default=None, help="Override max delay")
    p_batch.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    p_batch.set_defaults(func=cmd_batch)

    # Search subcommand
    p_search = subparsers.add_parser("search", help="Search catalog listings")
    p_search.add_argument("query", help="Search query string")
    p_search.add_argument("--location", default="all", help="Location slug (e.g. nizhniy_novgorod, msk, all)")
    p_search.add_argument("--page", type=int, default=1, help="Page number")
    p_search.add_argument("--proxy", help="Proxy URL")
    p_search.add_argument("--profile", choices=["stealth", "balanced", "fast_rotating", "datacenter"], default=None, help="Rate limit profile")
    p_search.add_argument("--min-delay", type=float, default=None)
    p_search.add_argument("--max-delay", type=float, default=None)
    p_search.add_argument("-v", "--verbose", action="store_true")
    p_search.set_defaults(func=cmd_search)

    # Test PoW subcommand
    p_pow = subparsers.add_parser("test-pow", help="Test PoW solving on live Avito")
    p_pow.add_argument("--proxy", help="Proxy URL")
    p_pow.set_defaults(func=cmd_test_pow)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
