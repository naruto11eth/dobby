from __future__ import annotations

from typing import List, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .data_models import ApplicationPlan, ApplicationAnswer, EventDetail
from .itinerary import build_itinerary
from .luma import LumaClient
from .preferences import EventPreferences
from .profile import UserProfile


console = Console()


def _format_price(event: EventDetail) -> str:
    candidates = []
    currencies = []
    for ticket in event.ticket_types:
        if ticket.price:
            candidates.append(ticket.price)
            if ticket.currency:
                currencies.append(ticket.currency.upper())
    info = event.ticket_info.get("price") if event.ticket_info else None
    if info and info.get("cents"):
        candidates.append(info["cents"] / 100)
        if info.get("currency"):
            currencies.append(info["currency"].upper())
    if not candidates:
        return "Free"
    currency = currencies[0] if currencies else "USD"
    minimum = min(candidates)
    maximum = max(candidates)
    if abs(maximum - minimum) < 0.01:
        return f"{minimum:.2f} {currency}"
    return f"{minimum:.2f}–{maximum:.2f} {currency}"


def _mode_label(event: EventDetail) -> str:
    mapping = {
        "paid": "Paid ticket",
        "full_application": "Application",
        "one_click": "Instant RSVP",
    }
    return mapping.get(event.registration_mode, event.registration_mode)


def _compute_autofill_score(event: EventDetail, missing: List[ApplicationAnswer]) -> float:
    required_total = len([q for q in event.registration_questions if q.required])
    if required_total == 0:
        return 1.0
    completed = required_total - len([ans for ans in missing if ans.required])
    return max(0.0, completed / required_total)


def _render_overview(plans: List[ApplicationPlan]) -> None:
    if not plans:
        console.print("No events matched your preferences.")
        return
    table = Table(title="Event Overview", show_lines=False)
    table.add_column("Event", style="bold")
    table.add_column("Date", no_wrap=True)
    table.add_column("Mode", no_wrap=True)
    table.add_column("Price", no_wrap=True)
    table.add_column("Hosts")
    table.add_column("Autofill", no_wrap=True)
    for plan in plans:
        event = plan.event
        date_display = event.start_local.strftime("%b %d • %I:%M %p")
        hosts = ", ".join(event.host_names) if event.host_names else "—"
        score_pct = f"{int(plan.autofill_score * 100)}%"
        missing_badge = "" if plan.autofill_score == 1.0 else f" ({len(plan.missing_required)} missing)"
        table.add_row(
            event.name,
            date_display,
            _mode_label(event),
            _format_price(event),
            hosts,
            score_pct + missing_badge,
        )
    console.print(table)


def _render_itinerary(plans: List[ApplicationPlan]) -> None:
    events = [plan.event for plan in plans]
    schedule = build_itinerary(events)
    if not schedule:
        return
    console.print("\nDaily itinerary based on selected events:")
    for day, items in schedule.items():
        console.rule(day)
        for event in items:
            start = event.start_local.strftime("%I:%M %p")
            end = event.end_local.strftime("%I:%M %p") if event.end_local else "—"
            console.print(
                f"[{start}-{end}] {event.name} • {_mode_label(event)} • {_format_price(event)} • {event.url}"
            )


def _render_application_details(plan: ApplicationPlan) -> None:
    event = plan.event
    table = Table(show_lines=False)
    table.add_column("Question")
    table.add_column("Answer")
    table.add_column("Source", no_wrap=True)
    for answer in plan.answers:
        table.add_row(
            answer.label,
            answer.answer or "[bold red]Missing[/bold red]",
            answer.source_field or "—",
        )
    summary = f"Mode: {_mode_label(event)} | Price: {_format_price(event)} | Missing required: {len(plan.missing_required)}"
    console.print(Panel(table, title=event.name, subtitle=summary, expand=False))


