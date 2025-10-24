from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from dateutil import parser

from .data_models import EventDetail


def parse_date_str(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return parser.isoparse(value).date()
    except (ValueError, TypeError):
        print("Could not parse date, ignoring.")
        return None


@dataclass
class EventPreferences:
    keywords: List[str] = field(default_factory=list)
    include_paid: bool = False
    include_full_applications: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def matches(self, event: EventDetail) -> bool:
        if not self.include_paid and event.is_paid:
            return False
        if not self.include_full_applications and event.registration_mode == "full_application":
            return False
        event_date = event.start_local.date()
        if self.start_date and event_date < self.start_date:
            return False
        if self.end_date and event_date > self.end_date:
            return False
        if self.keywords:
            haystack = " ".join(
                filter(
                    None,
                    [
                        event.name,
                        event.description or "",
                        " ".join(event.host_names),
                        " ".join(event.categories),
                        " ".join(event.tags),
                    ],
                )
            ).lower()
            if not any(keyword.lower() in haystack for keyword in self.keywords):
                return False
        return True


def collect_preferences() -> EventPreferences:
    print("\nTell me what kinds of events you want to prioritize.")
    keyword_input = input("Keywords to match (comma separated, leave blank for all): ").strip()
    keywords = [k.strip() for k in keyword_input.split(",") if k.strip()] if keyword_input else []
    include_paid = input("Include paid events? (y/N): ").strip().lower() in {"y", "yes"}
    include_full = input("Include application-heavy events that require approvals? (Y/n): ").strip().lower()
    include_full_applications = include_full not in {"n", "no"}
    start_date = parse_date_str(input("Earliest date to consider (YYYY-MM-DD, optional): ").strip())
    end_date = parse_date_str(input("Latest date to consider (YYYY-MM-DD, optional): ").strip())
    return EventPreferences(
        keywords=keywords,
        include_paid=include_paid,
        include_full_applications=include_full_applications,
        start_date=start_date,
        end_date=end_date,
    )
