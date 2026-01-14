from __future__ import annotations

import re
import random
import string
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple, Set

from rich.console import Console
from rich.table import Table

from .data_models import ApplicationAnswer, ApplicationPlan
from .profile import UserProfile

console = Console()


YES_VALUES = {"yes", "y", "true", "t", "1", "agree", "sure"}
NO_VALUES = {"no", "n", "false", "f", "0"}


@dataclass
class FieldFillResult:
    label: str
    value: Optional[str]
    status: str
    details: Optional[str] = None


@dataclass
class SubmissionResult:
    event_name: str
    url: str
    success: bool
    filled: List[FieldFillResult] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _try_import_playwright():
    try:
        from playwright.sync_api import Error, TimeoutError, sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install it with `pip install playwright` and run `playwright install`."
        ) from exc
    return Error, TimeoutError, sync_playwright


def _generate_random_value(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", label.strip().lower())[:16] or "field"
    token = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    lower = label.lower()
    if "email" in lower:
        return f"{slug}_{token}@example.com"
    if "phone" in lower or "whatsapp" in lower:
        return f"+1{random.randint(2000000000, 9999999999)}"
    if "telegram" in lower:
        return f"@{slug}{token}"
    if "discord" in lower:
        return f"{slug[:10]}#{random.randint(1000,9999)}"
    if "github" in lower:
        return f"{slug}{token}"
    if "linkedin" in lower or "profile" in lower or "url" in lower or "website" in lower:
        return f"https://example.com/{slug}-{token}"
    if "wallet" in lower or "address" in lower and "email" not in lower:
        return "0x" + "".join(random.choices("abcdef" + string.digits, k=40))
    if "age" in lower:
        return random.choice(["18-24", "25-34", "35-44"])
    if "country" in lower:
        return random.choice(["Argentina", "United States", "Lithuania"])
    return f"{slug}-{token}"
