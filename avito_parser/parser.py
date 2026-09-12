"""
High-accuracy HTML & JSON parser for Avito item pages and search listings.
Supports React Hydration state, Schema.org (JSON-LD), and OpenGraph fallbacks.
"""
import html as html_lib
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
    text = html_lib.unescape(text)
    text = text.replace('\xa0', ' ')
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

        # 3. Mobile Web (m.avito.ru) HTML fallback
        if not items:
            mobile_items, mobile_total = cls._parse_m_mobile(html, url=url)
            if mobile_items:
                items = mobile_items
                if total_count is None:
                    total_count = mobile_total

        return SearchResult(url=url, total_count=total_count, page=page, items=items)

    @classmethod
    def _parse_m_mobile(cls, html: str, url: str = "") -> Tuple[List[SearchResultItem], Optional[int]]:
        """
        Parses m.avito.ru catalog listing rendered without __staticRouterHydrationData items.
        """
        items: List[SearchResultItem] = []
        total_count = None

        count_match = re.search(r'page-title-count[^>]*>([0-9\s]+)', html) or re.search(r'(\d[\d\s]*)\s+объявлен', html)
        if count_match:
            try:
                total_count = int(re.sub(r'\D', '', count_match.group(1)))
            except ValueError:
                pass

        blocks = re.split(r'data-marker=["\']item["\']', html)[1:]
        for b in blocks:
            link_match = (
                re.search(r'item/link[^>]*href="([^"]+)"', b)
                or re.search(r'data-marker="item-title"[^>]*href="([^"]+)"', b)
                or re.search(r'href="(/[^"]+)"', b)
            )
            raw_link = link_match.group(1).strip() if link_match else ""
            item_url = re.sub(r'\?context=[^&]*(&|$)', '?', raw_link)
            item_url = item_url.split("?context")[0]
            if item_url.endswith("?") or item_url.endswith("&"):
                item_url = item_url[:-1]

            if item_url.startswith("https://m.avito.ru"):
                item_url = "https://www.avito.ru" + item_url[len("https://m.avito.ru"):]
            elif item_url.startswith("http://m.avito.ru"):
                item_url = "https://www.avito.ru" + item_url[len("http://m.avito.ru"):]
            elif item_url.startswith("/"):
                item_url = f"https://www.avito.ru{item_url}"
            elif item_url and not item_url.startswith("http"):
                item_url = urljoin("https://www.avito.ru", item_url)

            # Item ID
            id_match = re.search(r'_(\d+)(?:\?|$)', item_url) or re.search(r'data-item-id="(\d+)"', b)
            item_id = id_match.group(1) if id_match else ""

            # Title
            title_match = re.search(r'titleLabelGrid[^>]*>([^<]+)', b) or re.search(r'data-marker="item-title"[^>]*>([^<]+)', b)
            title = clean_html(title_match.group(1)) if title_match else ""

            # Price
            price_match = re.search(r'priceLabelGrid[^>]*>([^<]+)', b) or re.search(r'data-marker="item-price"[^>]*>([^<]+)', b)
            price_val = None
            fmt_price = "Цена не указана"
            if price_match:
                raw_p = clean_html(price_match.group(1))
                digits = re.sub(r'\D', '', raw_p)
                if digits:
                    price_val = int(digits)
                    fmt_price = f"{price_val:,} ₽".replace(",", " ")
                elif raw_p:
                    fmt_price = raw_p

            # Seller, Geo, Time
            geo_left = re.search(r'geoReferenceLeftLabel[^>]*>([^<]+)', b)
            geo_right = re.search(r'geoReferenceRightLabel[^>]*>([^<]+)', b)
            geo_parts = []
            if geo_left:
                geo_parts.append(clean_html(geo_left.group(1)))
            if geo_right:
                geo_parts.append(clean_html(geo_right.group(1)))
            location = ", ".join(geo_parts)

            time_m = re.search(r'sortTimeGrid[^>]*>([^<]+)', b)
            item_time = clean_html(time_m.group(1)) if time_m else ""

            if title or item_url:
                items.append(SearchResultItem(
                    id=item_id,
                    title=title,
                    price=price_val,
                    formatted_price=fmt_price,
                    url=item_url,
                    location=location,
                    time=item_time,
                ))

        # Fallback list zip if blocks split failed
        if not items:
            titles = re.findall(r'titleLabelGrid[^>]*>([^<]+)', html)
            prices = re.findall(r'priceLabelGrid[^>]*>([^<]+)', html)
            links = re.findall(r'item/link[^>]*href="([^"]+)"', html)
            for i, (t, p, l) in enumerate(zip(titles, prices, links)):
                raw_l = l.split("?context")[0]
                if raw_l.startswith("https://m.avito.ru"):
                    item_url = "https://www.avito.ru" + raw_l[len("https://m.avito.ru"):]
                elif raw_l.startswith("/"):
                    item_url = f"https://www.avito.ru{raw_l}"
                else:
                    item_url = raw_l
                id_m = re.search(r'_(\d+)(?:\?|$)', item_url)
                item_id = id_m.group(1) if id_m else str(i)
                digits = re.sub(r'\D', '', p)
                price_val = int(digits) if digits else None
                fmt_price = f"{price_val:,} ₽".replace(",", " ") if price_val is not None else p.strip()
                items.append(SearchResultItem(
                    id=item_id,
                    title=clean_html(t),
                    price=price_val,
                    formatted_price=fmt_price,
                    url=item_url,
                    location="",
                ))

        return items, total_count
