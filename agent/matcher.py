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
