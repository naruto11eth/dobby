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
