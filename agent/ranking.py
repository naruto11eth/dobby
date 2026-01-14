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


def rank_events(
    events: List["EventDetail"],
    profile: "UserProfile",
    ai_client: Optional["AIClient"] = None,
) -> List[RankedEvent]:
    """Rank events by relevance to user profile.

    Uses AI for semantic relevance scoring when ai_client is provided.
    Falls back to heuristic-only ranking otherwise.

    Combined score formula:
    - 50% AI relevance (or 0.5 default if no AI)
    - 30% guest popularity
    - 20% event quality

    Args:
        events: List of EventDetail objects to rank
        profile: User profile for relevance matching
        ai_client: Optional AIClient for semantic analysis

    Returns:
        List of RankedEvent sorted by combined_score descending
    """
    if not events:
        return []

    # Filter out paid events (user preference)
    free_events = [e for e in events if not e.is_paid]

    if not free_events:
        return []

    # Get AI relevance scores if client available
    ai_rankings: Dict[str, Dict] = {}
    if ai_client:
        try:
            rankings = ai_client.rank_events(free_events, profile)
            ai_rankings = {r["slug"]: r for r in rankings}
        except Exception:
            # Fallback to no AI rankings on error
            pass

    ranked_events: List[RankedEvent] = []
    for event in free_events:
        # Get AI relevance score (or default)
        ai_data = ai_rankings.get(event.slug, {})
        relevance_score = ai_data.get("relevance_score", 0.5)
        reasoning = ai_data.get("reasoning", "No AI analysis available")

        # Compute other scores
        guest_score = _compute_guest_score(event)
        quality_score = _compute_quality_score(event)

        # Weighted combination
        combined_score = (0.5 * relevance_score) + (0.3 * guest_score) + (0.2 * quality_score)

        ranked_events.append(
            RankedEvent(
                event=event,
                relevance_score=relevance_score,
                guest_score=guest_score,
                quality_score=quality_score,
                combined_score=combined_score,
                reasoning=reasoning,
            )
        )

    # Sort by combined score descending
    ranked_events.sort(key=lambda r: r.combined_score, reverse=True)

    return ranked_events


def filter_by_threshold(
    ranked_events: List[RankedEvent],
    threshold: float = 0.4,
) -> List[RankedEvent]:
    """Filter ranked events to only include those above a relevance threshold."""
    return [r for r in ranked_events if r.combined_score >= threshold]


def get_top_events(
    ranked_events: List[RankedEvent],
    limit: int = 10,
) -> List[RankedEvent]:
    """Get the top N ranked events."""
    return ranked_events[:limit]
