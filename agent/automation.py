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
        from playwright.sync_api import Error, TimeoutError, sync_playwright  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - handled at runtime
        raise RuntimeError(
            "Playwright is not installed. Install it with `pip install playwright` and run `playwright install`."
        ) from exc
    return Error, TimeoutError, sync_playwright


def _find_and_click_registration_trigger(page) -> bool:
    triggers: List[Tuple[str, str]] = [
        ("button", "Request to Join"),
        ("button", "Register"),
        ("button", "RSVP"),
        ("button", "Join Waitlist"),
        ("button", "Join Now"),
        ("button", "Apply"),
        ("button", "Get Tickets"),
        ("button", "Checkout"),
        ("button", "Continue"),
        ("button", "Purchase"),
        ("button", "Submit"),
        ("link", "Request to Join"),
        ("link", "Register"),
        ("link", "RSVP"),
    ]
    # ensure a ticket option is selected if presented as radio buttons
    try:
        page.get_by_role("radio").first.check(timeout=1500)
    except Exception:
        pass
    # quick CSS fallbacks to avoid slow timeouts
    css_triggers = [
        "button:has-text('Request to Join')",
        "button:has-text('Register')",
        "a:has-text('Request to Join')",
    ]
    for selector in css_triggers:
        try:
            page.locator(selector).first.click(timeout=800)
            return True
        except Exception:
            continue
    for role, text in triggers:
        locator = page.get_by_role(role, name=re.compile(text, re.IGNORECASE))
        try:
            locator.first.click(timeout=1000)
            return True
        except Exception:
            continue
    return False


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


def _find_element_handle(page, label: str):
    lowered = label.strip().lower()
    try:
        locator = page.get_by_label(label, exact=False)
        locator.wait_for(state="visible", timeout=1500)
        return locator.first
    except Exception:
        pass
    handle = page.evaluate_handle(
        """
(labelLower) => {
  const matches = (txt) => txt && txt.toLowerCase().includes(labelLower);
  const labels = Array.from(document.querySelectorAll('label'));
  for (const label of labels) {
    if (matches(label.textContent)) {
      const forId = label.getAttribute('for');
      if (forId) {
        const el = document.getElementById(forId);
        if (el) return el;
      }
      let scope = label;
      for (let depth = 0; depth < 4 && scope; depth++) {
        const nested = scope.querySelector('input, textarea, select, [contenteditable="true"], button[role="combobox"], button[data-headlessui-state], div[role="combobox"], button[aria-haspopup="listbox"], div[data-headlessui-state] button');
        if (nested) return nested;
        scope = scope.parentElement;
      }
    }
  }
  const placeholders = Array.from(document.querySelectorAll('[placeholder]'));
  for (const el of placeholders) {
    if (matches(el.getAttribute('placeholder'))) return el;
  }
  const aria = Array.from(document.querySelectorAll('[aria-label]'));
  for (const el of aria) {
    if (matches(el.getAttribute('aria-label'))) return el;
  }
  const legends = Array.from(document.querySelectorAll('legend'));
  for (const legend of legends) {
    if (matches(legend.textContent)) {
      const fieldset = legend.closest('fieldset');
      if (fieldset) {
        const el = fieldset.querySelector('input, textarea, select, button[role="combobox"], button[data-headlessui-state], div[role="combobox"], button[aria-haspopup="listbox"]');
        if (el) return el;
      }
    }
  }
  const comboCandidates = Array.from(document.querySelectorAll('button, div[role="combobox"], button[data-headlessui-state], button[aria-haspopup="listbox"], div[data-headlessui-state]'));
  for (const candidate of comboCandidates) {
    if (matches(candidate.textContent)) return candidate;
    const span = candidate.querySelector('span');
    if (span && matches(span.textContent)) return candidate;
  }
  const roleButtons = Array.from(document.querySelectorAll('[role="button"]'));
  for (const btn of roleButtons) {
    if (matches(btn.textContent)) return btn;
  }
  return null;
}
""",
        lowered,
    )
    return handle.as_element() if handle else None


MAIL_LIST_KEYWORDS = {
    "mailing list",
    "newsletter",
    "subscribe",
    "marketing",
    "updates",
    "email list",
}

CONSENT_KEYWORDS = {
    "agree",
    "privacy policy",
    "terms",
    "code of conduct",
    "consent",
    "policies",
    "waiver",
    "confirm",
}


def _candidate_strings(profile: UserProfile, label_lower: str) -> List[str]:
    candidates: List[str] = []
    if not profile:
        return candidates
    if any(keyword in label_lower for keyword in ["role", "describe", "background", "best describes"]):
        candidates.extend(
            filter(
                None,
                [
                    profile.role,
                    profile.preferred_name,
                    profile.project,
                    profile.company,
                    profile.bio,
                ],
            )
        )
    if any(keyword in label_lower for keyword in ["company", "organization", "team", "project"]):
        candidates.extend(filter(None, [profile.company, profile.project]))
    if "telegram" in label_lower:
        candidates.extend(filter(None, [profile.telegram]))
    if "discord" in label_lower:
        candidates.extend(filter(None, [profile.discord]))
    if any(keyword in label_lower for keyword in ["twitter", "x handle"]):
        candidates.extend(filter(None, [profile.twitter]))
    if "github" in label_lower:
        candidates.extend(filter(None, [profile.github]))
    return [c.lower() for c in candidates]


def _pick_option(
    options: List[Tuple[str, str]],
    desired: Optional[str],
    prefer_no: bool,
    prefer_yes: bool,
    random_fill: bool,
    candidates: Optional[List[str]] = None,
) -> Optional[Tuple[str, str]]:
    norm_desired = desired.lower() if desired else None

    def match_keywords(text: str, keywords: Sequence[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    normalized = [(value, label, (label or value or "").strip().lower()) for value, label in options]
    if norm_desired:
        for value, label, norm in normalized:
            if norm == norm_desired:
                return (value, label)
        for value, label, norm in normalized:
            if norm_desired in norm:
                return (value, label)
    if candidates:
        for value, label, norm in normalized:
            if any(candidate in norm for candidate in candidates):
                return (value, label)
    if prefer_no:
        for value, label, norm in normalized:
            if match_keywords(norm, ["no", "don't", "do not", "not now", "never"]):
                return (value, label)
    if prefer_yes:
        for value, label, norm in normalized:
            if match_keywords(norm, ["yes", "agree", "accept", "confirm", "sure"]):
                return (value, label)
    if normalized:
        return (normalized[0][0], normalized[0][1])
    return None


def _select_from_combobox(
    page,
    element,
    value: Optional[str],
    prefer_no: bool,
    prefer_yes: bool,
    random_fill: bool,
    candidates: Optional[List[str]] = None,
) -> Tuple[str, Optional[str]]:
    element.focus()
    element.click()
    try:
        page.wait_for_timeout(100)
    except Exception:
        pass
    selectors = [
        "div[data-floating-ui-portal] div[role='option']",
        "div[data-floating-ui-portal] li[role='option']",
        "div[data-floating-ui-portal] div.lux-menu-item",
        "div[role='listbox'] div[role='option']",
        "div[role='listbox'] li",
        "ul[role='listbox'] li",
    ]
    options: List[Tuple[object, str, str]] = []
    for selector in selectors:
        locator = page.locator(f"{selector}:visible")
        try:
            locator.first.wait_for(state="visible", timeout=1500)
        except Exception:
            continue
        count = locator.count()
        for idx in range(count):
            candidate = locator.nth(idx)
            try:
                text = candidate.inner_text().strip()
            except Exception:
                continue
            if not text:
                continue
            value_attr = candidate.get_attribute("data-value") or candidate.get_attribute("value") or text
            options.append((candidate, value_attr, text))
        if options:
            break

    if not options:
        try:
            element.press("ArrowDown")
            element.press("Enter")
            return ("filled", value or "")
        except Exception as exc:
            return ("skipped", f"No dropdown options visible: {exc}")

    structured = [(value_attr, label) for _, value_attr, label in options]
    selection = _pick_option(structured, value, prefer_no, prefer_yes, random_fill, candidates=candidates)
    chosen_value, chosen_label = selection or structured[0]

    for handle, option_value, option_label in options:
        if option_label == chosen_label or option_value == chosen_value:
            try:
                handle.scroll_into_view_if_needed(timeout=500)
            except Exception:
                pass
            try:
                handle.click()
            except Exception:
                try:
                    page.evaluate("arguments[0].click();", handle)
                except Exception:
                    continue
            return ("filled", option_label or option_value)

    try:
        element.fill(chosen_label or chosen_value)
        element.press("Enter")
        return ("filled", chosen_label or chosen_value)
    except Exception:
        return ("skipped", "Failed to select dropdown option")


def _fill_element(
    page,
    element,
    label: str,
    value: str,
    question_type: str,
    random_fill: bool,
    prefer_no: bool = False,
    prefer_yes: bool = False,
    candidates: Optional[List[str]] = None,
) -> Tuple[str, Optional[str]]:
    if element is None:
        return ("missing", "Element not found")
    try:
        tag = element.evaluate("el => el.tagName.toLowerCase()")
    except Exception as exc:
        return ("error", f"inspect failed: {exc}")
    try:
        if tag == "input":
            input_type = element.evaluate("el => (el.type || 'text').toLowerCase()")
            if input_type in {"checkbox", "radio"}:
                val = value.lower() if value else ""
                if prefer_yes:
                    element.check()
                    return ("filled", "checked")
                if prefer_no:
                    element.uncheck()
                    return ("filled", "unchecked")
                if val in YES_VALUES or (random_fill and val not in NO_VALUES):
                    element.check()
                    return ("filled", "checked")
                if val in NO_VALUES:
                    element.uncheck()
                    return ("filled", "unchecked")
                # default to check for required consent
                if "required" in (element.get_attribute("class") or "").lower():
                    element.check()
                    return ("filled", "checked")
                element.uncheck()
                return ("filled", "unchecked")
            if input_type == "file":
                return ("skipped", "File upload unsupported")
            element.fill(value)
            return ("filled", value)
        if tag == "textarea":
            element.fill(value)
            return ("filled", value)
        if tag == "select":
            options = element.evaluate(
                "el => Array.from(el.options).map(o => ({value: o.value, label: o.label}))"
            )
            structured = [(opt["value"], opt["label"]) for opt in options]
            selection = _pick_option(structured, value, prefer_no, prefer_yes, random_fill, candidates=candidates)
            if not selection:
                return ("skipped", f"No option for '{value}'")
            chosen_value, chosen_label = selection
            select_args = {}
            if chosen_value:
                select_args["value"] = chosen_value
            if chosen_label and not chosen_value:
                select_args["label"] = chosen_label
            if not select_args:
                select_args["index"] = 0
            element.select_option(**select_args)
            return ("filled", chosen_label or chosen_value)
        role = (element.get_attribute("role") or "").lower()
        has_listbox = element.get_attribute("aria-haspopup") == "listbox"
        if role == "combobox" or has_listbox:
            return _select_from_combobox(
                page,
                element,
                value,
                prefer_no,
                prefer_yes,
                random_fill,
                candidates=candidates,
            )
        if element.evaluate("el => el.getAttribute('contenteditable') === 'true'"):
            element.fill(value)
            return ("filled", value)
        element.fill(value)
        return ("filled", value)
    except Exception as exc:
        return ("error", str(exc))


def _fill_standard_fields(page, profile: UserProfile, random_fill: bool) -> List[FieldFillResult]:
    results: List[FieldFillResult] = []
    field_map = [
        ("Full name", profile.full_name),
        ("Name", profile.full_name),
        ("First name", profile.preferred_name or profile.full_name),
        ("Last name", profile.last_name),
        ("Email", profile.email),
        ("Email address", profile.email),
        ("Phone", profile.phone),
        ("Phone number", profile.phone),
        ("Company", profile.company),
        ("Organization", profile.company),
        ("Role", profile.role),
        ("Job title", profile.role),
        ("Title", profile.role),
        ("Telegram", profile.telegram),
        ("Discord", profile.discord),
        ("Twitter", profile.twitter),
        ("LinkedIn", profile.linkedin),
        ("Website", profile.website),
        ("Wallet", profile.wallet_address),
    ]
    for label, value in field_map:
        fill_value = value
        if not fill_value and random_fill:
            fill_value = _generate_random_value(label)
        if not fill_value:
            continue
        element = _find_element_handle(page, label)
        if not element:
            results.append(
                FieldFillResult(label=label, value=fill_value, status="skipped", details="Field not found")
            )
            continue
        label_lower = label.lower()
        prefer_no = any(keyword in label_lower for keyword in MAIL_LIST_KEYWORDS)
        prefer_yes = any(keyword in label_lower for keyword in CONSENT_KEYWORDS)
        status, details = _fill_element(
            page,
            element,
            label,
            fill_value,
            "text",
            random_fill,
            prefer_no=prefer_no,
            prefer_yes=prefer_yes,
            candidates=_candidate_strings(profile, label_lower),
        )
        results.append(FieldFillResult(label=label, value=fill_value, status=status, details=details))
    return results


def _fill_answer(page, answer: ApplicationAnswer, profile: UserProfile, random_fill: bool) -> FieldFillResult:
    label = answer.label
    original_value = answer.answer
    value = original_value
    generated = False
    label_lower = label.lower()
    prefer_no = any(keyword in label_lower for keyword in MAIL_LIST_KEYWORDS)
    prefer_yes = any(keyword in label_lower for keyword in CONSENT_KEYWORDS)
    candidates = _candidate_strings(profile, label_lower)
    if not value:
        if prefer_no:
            value = "no"
        elif prefer_yes:
            value = "yes"
        elif random_fill:
            if answer.question_type in {"single_select", "multi_select", "boolean", "checkbox"}:
                value = ""
            else:
                value = _generate_random_value(label)
                generated = True
    if not value and answer.question_type not in {"single_select", "multi_select", "boolean", "checkbox"}:
        return FieldFillResult(label=label, value=value, status="missing", details="No value provided")
    element = _find_element_handle(page, label)
    if not element:
        return FieldFillResult(label=label, value=value, status="skipped", details="Field not found")
    status, details = _fill_element(
        page,
        element,
        label,
        value,
        answer.question_type,
        random_fill,
        prefer_no=prefer_no,
        prefer_yes=prefer_yes,
        candidates=candidates,
    )
    if generated and status == "filled":
        return FieldFillResult(label=label, value=value, status="generated", details="Random value generated")
    return FieldFillResult(label=label, value=value, status=status, details=details)


def _attempt_submit(page) -> bool:
    submit_texts = [
        "Submit",
        "Register",
        "Complete",
        "Finish",
        "Join Waitlist",
        "Purchase Ticket",
        "Confirm",
    ]
    for text in submit_texts:
        locator = page.get_by_role("button", name=re.compile(text, re.IGNORECASE))
        try:
            locator.first.click(timeout=3000)
            page.wait_for_timeout(2000)
            return True
        except Exception:
            continue
    return False


def submit_with_playwright(
    plans: Sequence[ApplicationPlan],
    profile: UserProfile,
    headless: bool = True,
    manual_pause: bool = False,
    random_fill: bool = False,
) -> List[SubmissionResult]:
    Error, TimeoutError, sync_playwright = _try_import_playwright()
    results: List[SubmissionResult] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()

        for plan in plans:
            event = plan.event
            page = context.new_page()
            submission = SubmissionResult(event_name=event.name, url=event.url, success=False)
            console.print(f"\n[bold]Processing:[/bold] {event.name} ({event.url})")
            try:
                page.goto(event.url, timeout=60000)
                page.wait_for_load_state("networkidle")
            except TimeoutError as exc:
                submission.notes.append(f"Failed to load event page: {exc}")
                results.append(submission)
                continue

            opened = _find_and_click_registration_trigger(page)
            if not opened:
                submission.notes.append("Could not locate a registration/connect button automatically.")

            try:
                page.wait_for_selector("form", timeout=8000)
            except TimeoutError:
                submission.notes.append("Form did not appear; manual intervention required.")
                results.append(submission)
                continue

            submission.filled.extend(_fill_standard_fields(page, profile, random_fill=random_fill))

            for answer in plan.answers:
                field_result = _fill_answer(page, answer, profile, random_fill=random_fill)
                submission.filled.append(field_result)
                if answer.required and field_result.status not in {"filled", "generated"}:
                    submission.missing_required.append(answer.label)

            if plan.missing_required:
                submission.notes.append(
                    f"{len(plan.missing_required)} required answers were missing before automation; review manually."
                )

            if submission.missing_required:
                submission.notes.append("Some required fields were not filled automatically.")

            if manual_pause:
                console.print("Pausing for manual review. Close the tab or press Enter to continue...")
                input()

            submitted = _attempt_submit(page)
            if submitted and not submission.missing_required:
                submission.success = True
                submission.notes.append("Submission attempted; verify confirmation in browser.")
            else:
                submission.notes.append("Automatic submission incomplete; manual submission recommended.")

            results.append(submission)

        context.close()
        browser.close()
    return results


def render_submission_summary(results: Iterable[SubmissionResult]) -> None:
    table = Table(title="Automation Summary", show_lines=False)
    table.add_column("Event", style="bold")
    table.add_column("Result", no_wrap=True)
    table.add_column("Notes")
    for result in results:
        status = "Success" if result.success else "Manual review"
        notes = "; ".join(result.notes) if result.notes else "—"
        table.add_row(result.event_name, status, notes)
    console.print(table)
