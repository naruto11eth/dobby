from collections import defaultdict
from typing import Dict, List

from .data_models import EventDetail


def build_itinerary(events: List[EventDetail]) -> Dict[str, List[EventDetail]]:
    schedule: Dict[str, List[EventDetail]] = defaultdict(list)
    for event in sorted(events, key=lambda evt: evt.start_local):
        key = event.start_local.strftime("%Y-%m-%d (%A)")
        schedule[key].append(event)
    return dict(schedule)

