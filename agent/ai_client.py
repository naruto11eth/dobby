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

    def match_question_to_profile(
        self,
        question: RegistrationQuestion,
        profile: UserProfile,
    ) -> Dict[str, Any]:
        """Use Claude to semantically match a form question to profile fields.

        Returns dict with profile_field, value, confidence, reasoning.
        """
        profile_fields = {
            "full_name": profile.full_name,
            "email": profile.email,
            "preferred_name": profile.preferred_name,
            "last_name": profile.last_name,
            "phone": profile.phone,
            "telegram": profile.telegram,
            "discord": profile.discord,
            "twitter": profile.twitter,
            "github": profile.github,
            "linkedin": profile.linkedin,
            "website": profile.website,
            "company": profile.company,
            "role": profile.role,
            "bio": profile.bio,
            "location": profile.location,
            "city": profile.city,
            "country": profile.country,
            "wallet_address": profile.wallet_address,
            "solana_address": profile.solana_address,
            "ens": profile.ens,
            "project": profile.project,
            "dietary_preferences": profile.dietary_preferences,
            "tshirt_size": profile.tshirt_size,
            "pronouns": profile.pronouns,
        }
        # Filter out None values
        available_fields = {k: v for k, v in profile_fields.items() if v}

        prompt = f"""Match this form question to the most appropriate user profile field.

Form question: "{question.label}"
Question type: {question.question_type}
Required: {question.required}

Available profile fields and values:
{json.dumps(available_fields, indent=2)}

Return JSON with this exact format (no markdown, just raw JSON):
{{
  "profile_field": "field_name or null if no match",
  "value": "the value to use or null",
  "confidence": "high|medium|low",
  "reasoning": "Brief explanation of the match"
}}

If no good match exists, set profile_field and value to null.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "profile_field": None,
                "value": None,
                "confidence": "low",
                "reasoning": "Could not parse AI response",
            }

    def generate_answer(
        self,
        question: str,
        event_name: str,
        event_description: str,
        profile: UserProfile,
    ) -> str:
        """Generate a contextual answer for open-ended registration questions."""
        prompt = f"""Generate a brief, authentic answer for this event registration question.

Event: {event_name}
Event description: {event_description[:500] if event_description else 'No description available'}

Question: {question}

User profile:
- Name: {profile.full_name}
- Role: {profile.role or 'Not specified'}
- Company: {profile.company or 'Not specified'}
- Bio: {profile.bio or 'Not specified'}
- Project: {profile.project or 'Not specified'}

Requirements:
- Keep under 150 words
- Sound natural and professional
- Reference specific details from the event if relevant
- Highlight genuine alignment between user background and event topic
- Do not mention that this was AI-generated

Return ONLY the answer text, no quotes or formatting.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text.strip()

    def batch_match_questions(
        self,
        questions: List[RegistrationQuestion],
        profile: UserProfile,
    ) -> List[Dict[str, Any]]:
        """Match multiple questions to profile fields in a single API call for efficiency."""
        if not questions:
            return []

        profile_fields = {
            "full_name": profile.full_name,
            "email": profile.email,
            "preferred_name": profile.preferred_name,
            "last_name": profile.last_name,
            "phone": profile.phone,
            "telegram": profile.telegram,
            "discord": profile.discord,
            "twitter": profile.twitter,
            "github": profile.github,
            "linkedin": profile.linkedin,
            "website": profile.website,
            "company": profile.company,
            "role": profile.role,
            "bio": profile.bio,
            "location": profile.location,
            "city": profile.city,
            "country": profile.country,
            "wallet_address": profile.wallet_address,
            "solana_address": profile.solana_address,
            "ens": profile.ens,
            "project": profile.project,
            "dietary_preferences": profile.dietary_preferences,
            "tshirt_size": profile.tshirt_size,
            "pronouns": profile.pronouns,
        }
        available_fields = {k: v for k, v in profile_fields.items() if v}

        questions_data = [
            {"id": q.id, "label": q.label, "type": q.question_type, "required": q.required}
            for q in questions
        ]

        prompt = f"""Match these form questions to the most appropriate user profile fields.

Form questions (JSON):
{json.dumps(questions_data, indent=2)}

Available profile fields and values:
{json.dumps(available_fields, indent=2)}

For questions that ask for open-ended text (like "Why do you want to attend?" or "Tell us about yourself"),
generate an appropriate answer based on the user profile.

Return a JSON array with this exact format (no markdown, just raw JSON):
[
  {{
    "question_id": "id-1",
    "profile_field": "field_name or null",
    "value": "the value to use or generated answer",
    "confidence": "high|medium|low",
    "reasoning": "Brief explanation"
  }}
]
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: return empty matches
            return [
                {
                    "question_id": q.id,
                    "profile_field": None,
                    "value": None,
                    "confidence": "low",
                    "reasoning": "Could not parse AI response",
                }
                for q in questions
            ]
