from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, PrivateAttr

from .data_models import ApplicationAnswer, EventDetail, RegistrationQuestion
from .utils import normalize_label

PROFILE_PATH = Path("data/profile.json")


FIELD_ALIASES: Dict[str, str] = {
    "name": "full_name",
    "full_name": "full_name",
    "first_name": "preferred_name",
    "last_name": "last_name",
    "preferred_name": "preferred_name",
    "email": "email",
    "email_address": "email",
    "phone": "phone",
    "phone_number": "phone",
    "telegram": "telegram",
    "telegram_handle": "telegram",
    "telegram_username": "telegram",
    "discord": "discord",
    "discord_handle": "discord",
    "twitter": "twitter",
    "twitter_handle": "twitter",
    "x_handle": "twitter",
    "github": "github",
    "github_username": "github",
    "linkedin": "linkedin",
    "linkedin_url": "linkedin",
    "linkedin_profile": "linkedin",
    "website": "website",
    "site": "website",
    "portfolio": "website",
    "ens": "ens",
    "company": "company",
    "organisation": "company",
    "organization": "company",
    "employer": "company",
    "job_title": "role",
    "title": "role",
    "role": "role",
    "title_role": "role",
    "bio": "bio",
    "introduction": "bio",
    "about_you": "bio",
    "city": "city",
    "country": "country",
    "location": "location",
    "residence": "location",
    "wallet": "wallet_address",
    "wallet_address": "wallet_address",
    "eth_address": "wallet_address",
    "ethereum_address": "wallet_address",
    "solana_address": "solana_address",
    "telegram_id": "telegram",
    "pronouns": "pronouns",
    "dietary": "dietary_preferences",
    "dietary_requirements": "dietary_preferences",
    "dietary_preferences": "dietary_preferences",
    "shirt_size": "tshirt_size",
    "tshirt_size": "tshirt_size",
    "github_profile": "github",
}

SUBSTRING_FIELD_ALIASES: List[Tuple[str, str]] = [
    ("twitter", "twitter"),
    ("discord", "discord"),
    ("linkedin", "linkedin"),
    ("telegram", "telegram"),
    ("github", "github"),
    ("git", "github"),
    ("wallet", "wallet_address"),
    ("ens", "ens"),
    ("company", "company"),
    ("org", "company"),
    ("project", "project"),
]

QUESTION_TYPE_ALIASES: Dict[str, Iterable[str]] = {
    "email": ("email",),
    "mail": ("email",),
    "phone": ("phone",),
    "phone-number": ("phone",),
    "company": ("company",),
    "title": ("role",),
    "text": (),
    "paragraph": ("bio",),
    "github": ("github",),
    "twitter": ("twitter",),
    "url": ("website",),
}


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str
    email: str
    preferred_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None
    discord: Optional[str] = None
    twitter: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    wallet_address: Optional[str] = None
    solana_address: Optional[str] = None
    ens: Optional[str] = None
    project: Optional[str] = None
    dietary_preferences: Optional[str] = None
    tshirt_size: Optional[str] = None
    pronouns: Optional[str] = None
    custom_answers: Dict[str, str] = {}

    _storage_path: Path = PrivateAttr(default=PROFILE_PATH)

    @classmethod
    def load(cls, path: Path = PROFILE_PATH) -> Optional["UserProfile"]:
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        profile = cls.model_validate(data)
        profile._storage_path = path
        return profile

    @classmethod
    def create_interactively(cls, path: Path = PROFILE_PATH) -> "UserProfile":
        path.parent.mkdir(parents=True, exist_ok=True)
        print("Let's capture your base profile for event applications.")
        print("Press Enter to skip optional fields.")
        def ask(prompt: str, required: bool = False) -> str:
            while True:
                value = input(f"{prompt}: ").strip()
                if value or not required:
                    return value
                print("This field is required.")

        data = {
            "full_name": ask("Full name", required=True),
            "preferred_name": ask("Preferred name (optional)"),
            "email": ask("Email", required=True),
            "phone": ask("Primary phone or WhatsApp"),
            "telegram": ask("Telegram handle"),
            "discord": ask("Discord handle"),
            "twitter": ask("Twitter / X handle"),
            "github": ask("GitHub username"),
            "linkedin": ask("LinkedIn profile URL"),
            "website": ask("Website or portfolio"),
            "company": ask("Company or team"),
            "role": ask("Role / Title"),
            "bio": ask("Short bio"),
            "location": ask("Location (city, country)"),
            "wallet_address": ask("Primary wallet address (ETH)"),
            "solana_address": ask("Solana address"),
            "ens": ask("ENS name"),
            "project": ask("Project you represent"),
            "dietary_preferences": ask("Dietary preferences or restrictions"),
            "tshirt_size": ask("T-shirt size"),
            "pronouns": ask("Pronouns"),
        }
        profile = cls(**{k: (v or None) for k, v in data.items()})
        profile._storage_path = path
        profile.save()
        return profile

    @classmethod
    def load_or_create(cls, path: Path = PROFILE_PATH) -> "UserProfile":
        existing = cls.load(path)
        if existing:
            return existing
        return cls.create_interactively(path)

    def save(self, path: Optional[Path] = None) -> None:
        target = path or self._storage_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2))

    def _field_for_question(self, question: RegistrationQuestion) -> Optional[str]:
        key = normalize_label(question.label)
        if key in FIELD_ALIASES:
            return FIELD_ALIASES[key]
        for substring, field in SUBSTRING_FIELD_ALIASES:
            if substring in key:
                return field
        for candidate in QUESTION_TYPE_ALIASES.get(question.question_type, ()):
            return candidate
        return None

    def _resolve_question(
        self, question: RegistrationQuestion, event_name: str, interactive: bool
    ) -> Tuple[Optional[str], Optional[str]]:
        field = self._field_for_question(question)
        source = None
        value = None
        if field:
            source = field
            value = getattr(self, field, None)
        if value:
            return value, source
        key = normalize_label(question.label)
        if key in self.custom_answers:
            return self.custom_answers[key], f"custom:{key}"
        if interactive:
            prompt = f"[{event_name}] {question.label}"
            if question.required:
                prompt += " (required)"
            else:
                prompt += " (optional, leave blank to skip)"
            response = input(prompt + ": ").strip()
            if response:
                self.custom_answers[key] = response
                self.save()
                return response, f"custom:{key}"
        return None, source

    def build_application_answers(
        self,
        event: EventDetail,
        interactive: bool = True,
    ) -> Tuple[List[ApplicationAnswer], List[ApplicationAnswer]]:
        answers: List[ApplicationAnswer] = []
        missing: List[ApplicationAnswer] = []
        for question in event.registration_questions:
            response, source = self._resolve_question(question, event.name, interactive)
            app_answer = ApplicationAnswer(
                question_id=question.id,
                label=question.label,
                required=question.required,
                answer=response,
                question_type=question.question_type,
                source_field=source,
            )
            answers.append(app_answer)
            if question.required and not response:
                missing.append(app_answer)
        return answers, missing
