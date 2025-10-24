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


class EventDetail(BaseModel):
    api_id: str
    slug: str
    name: str
    description: Optional[str]
    description_raw: Optional[dict] = None
    start_at: datetime
    end_at: Optional[datetime]
    timezone: str
    location: Optional[str]
    location_mode: Optional[str]
    host_names: List[str] = Field(default_factory=list)
    ticket_types: List[TicketType] = Field(default_factory=list)
    registration_questions: List[RegistrationQuestion] = Field(default_factory=list)
    registration_requirements: Dict[str, bool] = Field(default_factory=dict)
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    ticket_info: Dict[str, Optional[object]] = Field(default_factory=dict)
    url: str
    source: str = "luma"

    @classmethod
    def from_event_payload(cls, payload: dict) -> "EventDetail":
        event = payload["event"]
        start_at = isoparse(event["start_at"])
        end_at = isoparse(event["end_at"]) if event.get("end_at") else None
        geo_info = event.get("geo_address_info") or {}
        location = first_non_empty(
            [
                geo_info.get("full_address"),
                geo_info.get("address"),
                geo_info.get("city_state"),
                geo_info.get("city"),
            ]
        )
        host_names = [host.get("name") for host in payload.get("hosts", []) if host.get("name")]
        categories = [cat.get("name") for cat in payload.get("categories", []) if cat.get("name")]
        tags = payload.get("tags") or []
        questions = [RegistrationQuestion.model_validate(q) for q in payload.get("registration_questions") or []]
        description_raw = payload.get("description_mirror")
        if isinstance(description_raw, dict):
            description = rich_text_to_plain(description_raw).strip()
        else:
            description = description_raw
        requirements = {
            "name": bool(payload.get("name_requirement")),
            "phone": bool(payload.get("phone_number_requirement")),
            "eth_address": bool(payload.get("eth_address_requirement")),
            "solana_address": bool(payload.get("solana_address_requirement")),
        }
        tickets = [TicketType.model_validate(ticket) for ticket in payload.get("ticket_types") or []]
        return cls(
            api_id=payload["api_id"],
            slug=event["url"],
            name=event["name"],
            description=description,
            description_raw=description_raw if isinstance(description_raw, dict) else None,
            start_at=start_at,
            end_at=end_at,
            timezone=event.get("timezone") or payload.get("timezone") or "UTC",
            location=location,
            location_mode=payload.get("geo_address_visibility"),
            host_names=host_names,
            ticket_types=tickets,
            registration_questions=questions,
            registration_requirements=requirements,
            categories=categories,
            tags=tags,
            ticket_info=payload.get("ticket_info") or {},
            url=f"https://luma.com/{event['url']}",
        )

    @property
    def tzinfo(self):
        return tz.gettz(self.timezone) or tz.UTC

    @property
    def start_local(self) -> datetime:
        return self.start_at.astimezone(self.tzinfo)

    @property
    def end_local(self) -> Optional[datetime]:
        if not self.end_at:
            return None
        return self.end_at.astimezone(self.tzinfo)

    @property
    def is_paid(self) -> bool:
        if self.ticket_info.get("is_free") is False:
            return True
        for ticket in self.ticket_types:
            if ticket.price and ticket.price > 0:
                return True
        return False

    @property
    def requires_approval(self) -> bool:
        if self.ticket_info.get("require_approval"):
            return True
        return any(ticket.require_approval for ticket in self.ticket_types)

    @property
    def registration_mode(self) -> str:
        if self.is_paid:
            return "paid"
        if self.requires_approval or self.registration_questions:
            return "full_application"
        return "one_click"


class ApplicationAnswer(BaseModel):
    question_id: str
    label: str
    required: bool
    answer: Optional[str]
    question_type: str
    source_field: Optional[str] = None


class ApplicationPlan(BaseModel):
    event: EventDetail
    answers: List[ApplicationAnswer]
    missing_required: List[ApplicationAnswer]
    autofill_score: float
