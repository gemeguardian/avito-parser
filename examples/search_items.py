"""
Example 3: Searching Avito catalog by keyword and city.
"""
from avito_parser import AvitoParser

def main():
    parser = AvitoParser(min_delay=2.0, max_delay=4.0)

    query = "ThinkBook 16GB"
    location = "nizhniy_novgorod"

    print(f"Searching for '{query}' in {location}...")
    results = parser.search(query, location=location, page=1)

    print(f"\nFound {results.total_count or len(results.items)} items on page {results.page}:")
    print("-" * 75)
    for it in results.items[:10]:
        print(f"• {it.title[:45]:<48} | {it.formatted_price:<12} | {it.location}")
    print("-" * 75)

if __name__ == "__main__":
    main()
