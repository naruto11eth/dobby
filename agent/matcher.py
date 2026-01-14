from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from pydantic import BaseModel

from .utils import normalize_label

if TYPE_CHECKING:
    from .ai_client import AIClient
    from .data_models import RegistrationQuestion
    from .profile import UserProfile


class FieldMatch(BaseModel):
    """Result of matching a form question to a profile field."""

    question_id: str
    question_label: str
    profile_field: Optional[str]  # Name of matched profile field, or None
    value: Optional[str]  # Value to fill, or None
    confidence: str  # "high", "medium", "low"
    reasoning: str  # Explanation for the match
    source: str  # "alias", "ai", "generated", "missing"
