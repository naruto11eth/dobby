from __future__ import annotations

import json
import time
import warnings
from typing import List, Optional

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL", category=Warning)

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import NotOpenSSLWarning

from .data_models import EventDetail, EventSummary


warnings.filterwarnings("ignore", category=NotOpenSSLWarning)


class LumaClient:
    base_url: str = "https://luma.com"

    def __init__(self, session: Optional[requests.Session] = None, request_delay: float = 0.0):
        self.session = session or requests.Session()
        self.request_delay = request_delay
        warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

    def _sleep_if_needed(self) -> None:
        if self.request_delay > 0:
            time.sleep(self.request_delay)

    def _build_url(self, slug: str) -> str:
        slug = slug.strip("/")
        return f"{self.base_url}/{slug}"

    def fetch_next_data(self, url: str) -> dict:
        self._sleep_if_needed()
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            raise RuntimeError(f"Could not locate __NEXT_DATA__ payload for {url}")
        return json.loads(script.string)

    def fetch_calendar_summaries(self, slug: str) -> List[EventSummary]:
        data = self.fetch_next_data(self._build_url(slug))
        payload = data["props"]["pageProps"]["initialData"]["data"]
        items = payload.get("featured_items") or []
        summaries = []
        for item in items:
            try:
                summaries.append(EventSummary.from_calendar_item(item))
            except Exception as exc:  # noqa: BLE001
                print(f"Failed to parse calendar item: {exc}")
        return summaries

    def fetch_event_detail(self, slug: str) -> EventDetail:
        data = self.fetch_next_data(self._build_url(slug))
        payload = data["props"]["pageProps"]["initialData"]["data"]
        return EventDetail.from_event_payload(payload)

    def fetch_events_with_details(self, slug: str) -> List[EventDetail]:
        summaries = self.fetch_calendar_summaries(slug)
        details: List[EventDetail] = []
        seen: set[str] = set()
        for summary in summaries:
            if summary.slug in seen:
                continue
            seen.add(summary.slug)
            try:
                details.append(self.fetch_event_detail(summary.slug))
            except Exception as exc:  # noqa: BLE001
                print(f"Failed to fetch details for {summary.slug}: {exc}")
        return details
