from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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

    def rank_events(
        self,
        events: List[EventDetail],
        profile: UserProfile,
    ) -> List[Dict[str, Any]]:
        """Rank events by relevance to user profile using Claude.

        Returns list of dicts with event_slug, relevance_score, reasoning.
        """
        if not events:
            return []

        event_summaries = []
        for event in events:
            summary = {
                "slug": event.slug,
                "name": event.name,
                "description": (event.description or "")[:500],
                "hosts": event.host_names,
                "categories": event.categories,
                "tags": event.tags,
            }
            event_summaries.append(summary)

        profile_context = {
            "role": profile.role,
            "company": profile.company,
            "bio": profile.bio,
            "project": profile.project,
            "interests": getattr(profile, "interests", None) or [],
        }

        prompt = f"""You are an AI assistant helping a crypto professional decide which events to attend.

User profile:
- Role: {profile_context['role'] or 'Not specified'}
- Company: {profile_context['company'] or 'Not specified'}
- Bio: {profile_context['bio'] or 'Not specified'}
- Project: {profile_context['project'] or 'Not specified'}

Events to rank (JSON):
{json.dumps(event_summaries, indent=2)}

For each event, determine how relevant it is to this user based on their profile.
Consider: topic alignment, networking value, learning opportunities.

Return a JSON array with this exact format (no markdown, just raw JSON):
[
  {{"slug": "event-slug-1", "relevance_score": 0.85, "reasoning": "Brief explanation"}},
  {{"slug": "event-slug-2", "relevance_score": 0.60, "reasoning": "Brief explanation"}}
]

Sort by relevance_score descending. Score range is 0.0 to 1.0.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Handle potential markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            rankings = json.loads(text)
            return rankings
        except json.JSONDecodeError:
            # Fallback: return events in original order with neutral scores
            return [
                {"slug": e.slug, "relevance_score": 0.5, "reasoning": "Could not parse AI response"}
                for e in events
            ]
