"""
High-accuracy HTML & JSON parser for Avito item pages and search listings.
Supports React Hydration state, Schema.org (JSON-LD), and OpenGraph fallbacks.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from .models import AvitoItem, ItemParam, SearchResult, SearchResultItem, SellerInfo

logger = logging.getLogger(__name__)


def clean_html(text: Optional[str]) -> str:
    """Strip HTML tags and unescape common entities."""
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = (
        text.replace('&nbsp;', ' ')
        .replace('&#39;', "'")
        .replace('&quot;', '"')
        .replace('&amp;', '&')
        .replace('&lt;', '<')
        .replace('&gt;', '>')
    )
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class AvitoItemParser:
    """
    Extracts structured AvitoItem from item page HTML.
    """

    @classmethod
    def parse(cls, html: str, url: str = "") -> Optional[AvitoItem]:
        # Extract ID from URL if available
        item_id = ""
        id_match = re.search(r'_(\d+)(?:\?|$)', url)
        if id_match:
            item_id = id_match.group(1)

        # 1. Attempt parsing from window.__staticRouterHydrationData (Redux state)
        item = cls._parse_from_hydration(html, item_id, url)
        if item:
            return item

        # 2. Attempt parsing from Schema.org (JSON-LD)
        item = cls._parse_from_json_ld(html, item_id, url)
        if item:
            return item

        # 3. Fallback meta tag extraction
        return cls._parse_from_meta(html, item_id, url)

    @classmethod
    def _parse_from_hydration(cls, html: str, item_id: str, url: str) -> Optional[AvitoItem]:
        m = re.search(r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\(\"(.*?)\"\);', html)
        if not m:
            return None

        try:
            raw_escaped = json.loads('"' + m.group(1) + '"')
            hdata = json.loads(raw_escaped)
            loader = hdata.get("loaderData", {})

            # Locate buyerItem
            buyer_item = None
            for key, val in loader.items():
                if isinstance(val, dict) and "buyerItem" in val:
                    buyer_item = val["buyerItem"]
                    break

            if not buyer_item:
                return None

            item_data = buyer_item.get("item", {})
            if not item_data:
                return None

            extracted_id = str(item_data.get("id") or item_id)
            title = item_data.get("title", "")
            price = item_data.get("price")
            desc = clean_html(item_data.get("description", ""))
            address = item_data.get("address", "")

            # City extraction
            city = ""
            if address:
                city = address.split(",")[0].strip()

            # Seller info
            seller_obj = buyer_item.get("seller", {})
            rating_obj = buyer_item.get("rating", {})
            seller = SellerInfo(
                name=seller_obj.get("name", "") if isinstance(seller_obj, dict) else "",
                rating=float(rating_obj.get("score")) if rating_obj and rating_obj.get("score") else None,
                reviews_count=int(rating_obj.get("itemReviewCount")) if rating_obj and rating_obj.get("itemReviewCount") else None,
                seller_type="Магазин" if buyer_item.get("isCompany") else "Частное лицо",
            )

            # Parameters
            params: Dict[str, str] = {}
            params_block = buyer_item.get("paramsBlock", {})
            for p in params_block.get("items", []):
                t = p.get("title")
                d = p.get("description")
                if t and d:
                    params[t] = str(d).strip()

            # Images
            images: List[str] = []
            for img in item_data.get("images", []):
                if isinstance(img, dict):
                    # Pick highest resolution
                    variants = img.get("variants", {})
                    if variants:
                        highest = list(variants.values())[-1]
                        images.append(highest)
                    elif img.get("url"):
                        images.append(img["url"])

            # Formatted price
            formatted_price = f"{price:,} ₽".replace(",", " ") if price is not None else "Цена не указана"

            return AvitoItem(
                id=extracted_id,
                title=title,
                url=url or f"https://www.avito.ru/{extracted_id}",
                price=price,
                currency="RUB",
                formatted_price=formatted_price,
                address=address,
                city=city,
                seller=seller,
                params=params,
                description=desc,
                images=images,
                category=buyer_item.get("rootCategorySlug", ""),
                is_active=item_data.get("isActive", True),
                raw_data=item_data,
            )

        except Exception as e:
            logger.debug("Failed parsing hydration data: %s", e)
            return None

    @classmethod
    def _parse_from_json_ld(cls, html: str, item_id: str, url: str) -> Optional[AvitoItem]:
        m_ld = re.search(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m_ld:
            return None

        try:
            ld = json.loads(m_ld.group(1))
            graph = ld.get("@graph", [ld])
            for elem in graph:
                if elem.get("@type") == "Product":
                    title = elem.get("name", "")
                    desc = clean_html(elem.get("description", ""))
                    sku = str(elem.get("sku") or item_id)
                    offers = elem.get("offers", {})
                    price = None
                    currency = "RUB"
                    if isinstance(offers, dict) and offers.get("price"):
                        price = int(float(offers["price"]))
                        currency = offers.get("priceCurrency", "RUB")

                    formatted_price = f"{price:,} {currency}".replace(",", " ") if price is not None else "Цена не указана"

                    # Parse images
                    images = []
                    raw_img = elem.get("image")
                    if isinstance(raw_img, list):
                        images = raw_img
                    elif isinstance(raw_img, str):
                        images = [raw_img]

                    # Parse seller from meta if available
                    seller = cls._extract_seller_meta(html)

                    return AvitoItem(
                        id=sku,
                        title=title,
                        url=url,
                        price=price,
                        currency=currency,
                        formatted_price=formatted_price,
                        seller=seller,
                        description=desc,
                        images=images,
                    )
        except Exception as e:
            logger.debug("Failed parsing JSON-LD: %s", e)

        return None

    @classmethod
    def _parse_from_meta(cls, html: str, item_id: str, url: str) -> Optional[AvitoItem]:
        title = ""
        tm = re.search(r'<title[^>]*>(.*?)</title>', html)
        if tm:
            title = tm.group(1).split("—")[0].split("|")[0].strip()

        if not title:
            return None

        desc = ""
        dm = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if dm:
            desc = clean_html(dm.group(1))

        seller = cls._extract_seller_meta(html)

        return AvitoItem(
            id=item_id,
            title=title,
            url=url,
            seller=seller,
            description=desc,
        )

    @staticmethod
    def _extract_seller_meta(html: str) -> SellerInfo:
        seller_name = ""
        rating_val = None
        count_val = None

        sm = re.search(r'<meta[^>]*property="vk:seller_name"[^>]*content="([^"]*)"', html)
        if sm:
            seller_name = sm.group(1).strip()

        rm = re.search(r'<meta[^>]*property="vk:seller_rating"[^>]*content="([^"]*)"', html)
        if rm and rm.group(1).strip():
            try:
                rating_val = float(rm.group(1).strip())
            except ValueError:
                pass

        cm = re.search(r'<meta[^>]*property="vk:seller_review_count"[^>]*content="([^"]*)"', html)
        if cm and cm.group(1).strip():
            try:
                count_val = int(cm.group(1).strip())
            except ValueError:
                pass

        return SellerInfo(name=seller_name, rating=rating_val, reviews_count=count_val)


class AvitoCatalogParser:
    """
    Parses search results / catalog pages to retrieve item listings.
    """

    @classmethod
    def parse(cls, html: str, url: str = "") -> SearchResult:
        items: List[SearchResultItem] = []
        total_count = None
        page = 1

        # 1. Try staticRouterHydrationData
        m = re.search(r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\(\"(.*?)\"\);', html)
        if m:
            try:
                raw_escaped = json.loads('"' + m.group(1) + '"')
                hdata = json.loads(raw_escaped)
                loader = hdata.get("loaderData", {})
                for k, v in loader.items():
                    if isinstance(v, dict):
                        # check catalog items
                        catalog = v.get("catalog", {}) or v.get("items", {})
                        if isinstance(catalog, dict) and "items" in catalog:
                            total_count = catalog.get("count")
                            for it in catalog.get("items", []):
                                if isinstance(it, dict) and it.get("id"):
                                    price_val = it.get("price") or it.get("priceDetailed", {}).get("value")
                                    fmt_price = f"{price_val:,} ₽".replace(",", " ") if price_val else "Цена не указана"
                                    item_url = it.get("urlPath") or it.get("url") or f"/{it['id']}"
                                    items.append(SearchResultItem(
                                        id=str(it["id"]),
                                        title=it.get("title", ""),
                                        price=price_val,
                                        formatted_price=fmt_price,
                                        url=urljoin("https://www.avito.ru", item_url),
                                        location=it.get("geo", {}).get("geoReferences", [{}])[0].get("content", ""),
                                        time=it.get("sortFormatedDate", ""),
                                    ))
            except Exception as e:
                logger.debug("Failed catalog hydration parse: %s", e)

        # 2. Schema.org ItemList fallback
        if not items:
            m_ld = re.search(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL)
            if m_ld:
                try:
                    ld = json.loads(m_ld.group(1))
                    graph = ld.get("@graph", [ld])
                    for elem in graph:
                        if elem.get("@type") == "ItemList":
                            for pos in elem.get("itemListElement", []):
                                prod = pos.get("item", {})
                                if prod.get("@type") == "Product":
                                    offers = prod.get("offers", {})
                                    price_val = int(offers.get("price")) if offers.get("price") else None
                                    fmt = f"{price_val:,} ₽".replace(",", " ") if price_val else ""
                                    items.append(SearchResultItem(
                                        id=str(prod.get("sku", "")),
                                        title=prod.get("name", ""),
                                        price=price_val,
                                        formatted_price=fmt,
                                        url=offers.get("url") or prod.get("url", ""),
                                        location="",
                                    ))
                except Exception:
                    pass

        return SearchResult(url=url, total_count=total_count, page=page, items=items)
