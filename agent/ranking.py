from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from .ai_client import AIClient
    from .data_models import EventDetail
    from .profile import UserProfile


class RankedEvent(BaseModel):
    """An event with AI-generated relevance scoring."""

    event: "EventDetail"
    relevance_score: float  # 0.0 - 1.0 from AI analysis
    guest_score: float  # Normalized guest count
    quality_score: float  # Description, cover image, host quality
    combined_score: float  # Weighted combination
    reasoning: str  # AI explanation for the ranking

    class Config:
        arbitrary_types_allowed = True


def _compute_guest_score(event: "EventDetail") -> float:
    """Compute normalized guest score based on registered tickets."""
    max_guests = 0
    for ticket in event.ticket_types:
        if ticket.num_tickets_registered:
            max_guests = max(max_guests, ticket.num_tickets_registered)

    if max_guests == 0:
        return 0.3  # Default moderate score for events without guest data

    # Normalize: 100+ guests = 1.0, scale down from there
    return min(1.0, max_guests / 100)


def _compute_quality_score(event: "EventDetail") -> float:
    """Compute quality score based on event metadata richness."""
    score = 0.0

    # Has description (30% weight)
    if event.description and len(event.description) > 50:
        score += 0.3
    elif event.description:
        score += 0.15

    # Has hosts listed (20% weight)
    if event.host_names:
        score += 0.2

    # Has categories/tags (20% weight)
    if event.categories or event.tags:
        score += 0.2

    # Has location specified (15% weight)
    if event.location:
        score += 0.15

    # Has end time (indicates well-planned event) (15% weight)
    if event.end_at:
        score += 0.15

    return score
