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


# Fast lookup for common field mappings (used before AI fallback)
FAST_FIELD_ALIASES: Dict[str, str] = {
    "name": "full_name",
    "full_name": "full_name",
    "fullname": "full_name",
    "first_name": "preferred_name",
    "firstname": "preferred_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "email": "email",
    "email_address": "email",
    "phone": "phone",
    "phone_number": "phone",
    "telegram": "telegram",
    "discord": "discord",
    "twitter": "twitter",
    "x_handle": "twitter",
    "github": "github",
    "linkedin": "linkedin",
    "website": "website",
    "company": "company",
    "organization": "company",
    "organisation": "company",
    "role": "role",
    "job_title": "role",
    "title": "role",
    "bio": "bio",
    "wallet": "wallet_address",
    "wallet_address": "wallet_address",
    "eth_address": "wallet_address",
    "solana_address": "solana_address",
    "ens": "ens",
    "project": "project",
    "dietary": "dietary_preferences",
    "tshirt": "tshirt_size",
    "shirt_size": "tshirt_size",
    "pronouns": "pronouns",
    "location": "location",
    "city": "city",
    "country": "country",
}


def _try_alias_match(
    question: "RegistrationQuestion",
    profile: "UserProfile",
) -> Optional[FieldMatch]:
    """Attempt fast alias-based matching before using AI."""
    normalized = normalize_label(question.label)

    # Check exact alias match
    if normalized in FAST_FIELD_ALIASES:
        field = FAST_FIELD_ALIASES[normalized]
        value = getattr(profile, field, None)
        if value:
            return FieldMatch(
                question_id=question.id,
                question_label=question.label,
                profile_field=field,
                value=value,
                confidence="high",
                reasoning=f"Exact alias match: {normalized} -> {field}",
                source="alias",
            )

    # Check substring matches for common patterns
    label_lower = question.label.lower()
    for pattern, field in [
        ("telegram", "telegram"),
        ("discord", "discord"),
        ("twitter", "twitter"),
        ("github", "github"),
        ("linkedin", "linkedin"),
        ("wallet", "wallet_address"),
        ("email", "email"),
        ("phone", "phone"),
        ("company", "company"),
        ("project", "project"),
    ]:
        if pattern in label_lower:
            value = getattr(profile, field, None)
            if value:
                return FieldMatch(
                    question_id=question.id,
                    question_label=question.label,
                    profile_field=field,
                    value=value,
                    confidence="high",
                    reasoning=f"Substring match: '{pattern}' found in label",
                    source="alias",
                )

    return None


def match_questions_to_profile(
    questions: List["RegistrationQuestion"],
    profile: "UserProfile",
    ai_client: Optional["AIClient"] = None,
    event_name: str = "",
    event_description: str = "",
) -> List[FieldMatch]:
    """Match form questions to profile fields using alias matching + AI fallback."""
    matches: List[FieldMatch] = []
    unmatched: List["RegistrationQuestion"] = []

    # First pass: try alias matching
    for question in questions:
        alias_match = _try_alias_match(question, profile)
        if alias_match:
            matches.append(alias_match)
        else:
            unmatched.append(question)

    # Second pass: use AI for unmatched questions
    if unmatched and ai_client:
        try:
            ai_matches = ai_client.batch_match_questions(unmatched, profile)
            ai_matches_by_id = {m["question_id"]: m for m in ai_matches}

            for question in unmatched:
                ai_data = ai_matches_by_id.get(question.id, {})
                value = ai_data.get("value")
                profile_field = ai_data.get("profile_field")
                confidence = ai_data.get("confidence", "low")
                reasoning = ai_data.get("reasoning", "No AI analysis")

                # If AI couldn't find a match and it's an open-ended question,
                # try to generate an answer
                if not value and _is_open_ended_question(question):
                    try:
                        value = ai_client.generate_answer(
                            question.label,
                            event_name,
                            event_description,
                            profile,
                        )
                        source = "generated"
                        confidence = "medium"
                        reasoning = "AI-generated answer for open-ended question"
                    except Exception:
                        source = "missing"
                else:
                    source = "ai" if value else "missing"

                matches.append(
                    FieldMatch(
                        question_id=question.id,
                        question_label=question.label,
                        profile_field=profile_field,
                        value=value,
                        confidence=confidence,
                        reasoning=reasoning,
                        source=source,
                    )
                )
        except Exception:
            # AI failed, mark all unmatched as missing
            for question in unmatched:
                matches.append(
                    FieldMatch(
                        question_id=question.id,
                        question_label=question.label,
                        profile_field=None,
                        value=None,
                        confidence="low",
                        reasoning="AI matching failed",
                        source="missing",
                    )
                )
    else:
        # No AI client, mark unmatched as missing
        for question in unmatched:
            matches.append(
                FieldMatch(
                    question_id=question.id,
                    question_label=question.label,
                    profile_field=None,
                    value=None,
                    confidence="low",
                    reasoning="No AI client available for semantic matching",
                    source="missing",
                )
            )

    return matches


def _is_open_ended_question(question: "RegistrationQuestion") -> bool:
    """Check if a question is open-ended (requires generated text answer)."""
    open_ended_types = {"paragraph", "textarea", "text"}
    if question.question_type.lower() in open_ended_types:
        return True

    # Also check for common open-ended question patterns in the label
    label_lower = question.label.lower()
    open_ended_patterns = [
        "why do you",
        "tell us about",
        "describe",
        "what are you",
        "what do you",
        "how did you",
        "what brings you",
        "share",
        "explain",
    ]
    return any(pattern in label_lower for pattern in open_ended_patterns)


def get_missing_required(matches: List[FieldMatch]) -> List[FieldMatch]:
    """Get list of required questions that couldn't be matched."""
    return [m for m in matches if m.source == "missing"]


def compute_autofill_score(matches: List[FieldMatch], total_required: int) -> float:
    """Compute percentage of questions that can be autofilled."""
    if total_required == 0:
        return 1.0
    filled = len([m for m in matches if m.value is not None])
    return filled / len(matches) if matches else 0.0
