"""
Data models for avito-parser.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class ItemParam:
    title: str
    value: str

    def to_dict(self) -> Dict[str, str]:
        return {"title": self.title, "value": self.value}


@dataclass
class SellerInfo:
    name: str = ""
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    seller_type: str = ""  # e.g., "Частное лицо", "Компания"
    profile_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AvitoItem:
    id: str
    title: str
    url: str
    price: Optional[int] = None
    currency: str = "RUB"
    formatted_price: str = ""
    address: str = ""
    city: str = ""
    seller: SellerInfo = field(default_factory=SellerInfo)
    params: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    images: List[str] = field(default_factory=list)
    category: str = ""
    is_active: bool = True
    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        res = {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "price": self.price,
            "currency": self.currency,
            "formatted_price": self.formatted_price,
            "address": self.address,
            "city": self.city,
            "seller": self.seller.to_dict(),
            "params": self.params,
            "description": self.description,
            "images": self.images,
            "category": self.category,
            "is_active": self.is_active,
        }
        if include_raw and self.raw_data:
            res["raw_data"] = self.raw_data
        return res


@dataclass
class SearchResultItem:
    id: str
    title: str
    price: Optional[int]
    formatted_price: str
    url: str
    location: str
    time: str = ""
    image_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    url: str
    total_count: Optional[int] = None
    page: int = 1
    items: List[SearchResultItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "total_count": self.total_count,
            "page": self.page,
            "items": [it.to_dict() for it in self.items],
        }
