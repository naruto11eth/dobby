from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from anthropic import Anthropic

if TYPE_CHECKING:
    from .data_models import EventDetail, RegistrationQuestion
    from .profile import UserProfile


class AIClient:
    """Wrapper around Anthropic Claude API for event ranking and form filling."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable or pass --api-key flag."
            )
        self.client = Anthropic(api_key=key)
        self.model = "claude-sonnet-4-20250514"
