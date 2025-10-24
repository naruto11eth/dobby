from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from dateutil import tz
from dateutil.parser import isoparse
from pydantic import BaseModel, Field

from .utils import first_non_empty, rich_text_to_plain


class RegistrationQuestion(BaseModel):
    id: str
    label: str
    required: bool
    question_type: str = Field(alias="question_type")


class TicketType(BaseModel):
    api_id: str
    name: str
    cents: Optional[int]
    currency: Optional[str]
    type: str
    require_approval: bool = False
    is_hidden: bool = False
    is_disabled: bool = False
    num_tickets_registered: Optional[int] = None
    description: Optional[str] = None
    min_cents: Optional[int] = None
    max_capacity: Optional[int] = None

    @property
    def price(self) -> Optional[float]:
        if self.cents is None:
            return None
        return self.cents / 100


class EventSummary(BaseModel):
    slug: str
    name: str
    start_at: datetime
    end_at: Optional[datetime]
    timezone: str
    location: Optional[str]
    cover_url: Optional[str]
    calendar_name: Optional[str]
    is_free: Optional[bool]
    require_approval: Optional[bool]
    price: Optional[float]
    platform: str = "luma"

    @classmethod
    def from_calendar_item(cls, item: dict) -> "EventSummary":
        event = item["event"]
        ticket_info = item.get("ticket_info") or {}
        start_at = isoparse(event["start_at"])
        end_at = isoparse(event["end_at"]) if event.get("end_at") else None
        location = None
        geo_info = event.get("geo_address_info") or {}
        location = first_non_empty(
            [
                geo_info.get("full_address"),
                geo_info.get("address"),
                geo_info.get("city_state"),
                geo_info.get("city"),
            ]
        )
        price_cents = None
        if ticket_info.get("price"):
            price_cents = ticket_info["price"].get("cents")
        if price_cents is None and ticket_info.get("max_price"):
            price_cents = ticket_info["max_price"].get("cents")
        price = price_cents / 100 if price_cents else None
        return cls(
            slug=event["url"],
            name=event["name"],
            start_at=start_at,
            end_at=end_at,
            timezone=event.get("timezone") or item["calendar"].get("timezone") or "UTC",
            location=location,
            cover_url=event.get("cover_url"),
            calendar_name=item["calendar"].get("name"),
            is_free=ticket_info.get("is_free"),
            require_approval=ticket_info.get("require_approval"),
            price=price,
        )


