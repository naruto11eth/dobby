from __future__ import annotations

from typing import List, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .automation import render_submission_summary, submit_with_playwright
from .data_models import ApplicationAnswer, ApplicationPlan, EventDetail
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


def _render_ranked_events(ranked_events: list) -> None:
    """Render AI-ranked events with scores and reasoning."""
    if not ranked_events:
        console.print("No events to display.")
        return

    table = Table(title="AI-Ranked Events (by relevance to your profile)", show_lines=False)
    table.add_column("#", justify="right", style="bold")
    table.add_column("Event")
    table.add_column("Score", no_wrap=True)
    table.add_column("Date", no_wrap=True)
    table.add_column("Mode", no_wrap=True)
    table.add_column("AI Reasoning", max_width=50)

    for idx, ranked in enumerate(ranked_events, start=1):
        event = ranked.event
        score_display = f"{ranked.combined_score:.0%}"
        date_display = event.start_local.strftime("%b %d • %I:%M %p")
        # Truncate reasoning if too long
        reasoning = ranked.reasoning[:47] + "..." if len(ranked.reasoning) > 50 else ranked.reasoning
        table.add_row(
            str(idx),
            event.name,
            score_display,
            date_display,
            _mode_label(event),
            reasoning,
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


def _render_selection_table(events: Sequence[EventDetail]) -> None:
    table = Table(title="Available Events", show_lines=False)
    table.add_column("#", justify="right", style="bold")
    table.add_column("Event")
    table.add_column("Date", no_wrap=True)
    table.add_column("Mode", no_wrap=True)
    table.add_column("Price", no_wrap=True)
    table.add_column("Slug", no_wrap=True)
    for idx, event in enumerate(events, start=1):
        table.add_row(
            str(idx),
            event.name,
            event.start_local.strftime("%b %d • %I:%M %p"),
            _mode_label(event),
            _format_price(event),
            event.slug,
        )
    console.print(table)


def _select_events(
    events: Sequence[EventDetail],
    interactive: bool,
    select_all: bool,
    chosen_slugs: Optional[List[str]],
) -> List[EventDetail]:
    if not events:
        return []
    slug_map = {event.slug: event for event in events}
    if select_all:
        console.print("Selecting all fetched events.")
        return list(events)
    if chosen_slugs:
        missing = [slug for slug in chosen_slugs if slug not in slug_map]
        if missing:
            console.print(f"[yellow]Warning:[/yellow] Unknown slugs {missing} were ignored.")
        selected = [slug_map[slug] for slug in chosen_slugs if slug in slug_map]
        if selected:
            return selected
        console.print("No valid slugs provided; falling back to manual selection.")
    if not interactive:
        console.print(
            "[red]Non-interactive mode[/red] requires either `--select-all` or explicit `--events` slugs."
        )
        return []
    _render_selection_table(events)
    while True:
        response = console.input(
            "Enter event numbers separated by commas (press Enter for all, or type 'all'): "
        ).strip()
        if not response or response.lower() == "all":
            return list(events)
        try:
            indices = [int(part.strip()) for part in response.split(",") if part.strip()]
        except ValueError:
            console.print("[red]Invalid input.[/red] Please enter numbers separated by commas.")
            continue
        selected: List[EventDetail] = []
        for idx in indices:
            if 1 <= idx <= len(events):
                selected.append(events[idx - 1])
            else:
                console.print(f"[yellow]Ignoring out-of-range index:[/yellow] {idx}")
        if selected:
            return selected
        console.print("No valid selections made. Try again or press Enter for all.")


def _select_from_ranked(
    ranked_events: list,
    interactive: bool,
    select_all: bool,
    chosen_slugs: Optional[List[str]],
) -> List[EventDetail]:
    """Select events from AI-ranked list."""
    if not ranked_events:
        return []

    events = [r.event for r in ranked_events]
    slug_map = {event.slug: event for event in events}

    if select_all:
        console.print("Selecting all ranked events.")
        return events

    if chosen_slugs:
        missing = [slug for slug in chosen_slugs if slug not in slug_map]
        if missing:
            console.print(f"[yellow]Warning:[/yellow] Unknown slugs {missing} were ignored.")
        selected = [slug_map[slug] for slug in chosen_slugs if slug in slug_map]
        if selected:
            return selected
        console.print("No valid slugs provided; falling back to manual selection.")

    if not interactive:
        console.print(
            "[red]Non-interactive mode[/red] requires either `--select-all` or explicit `--events` slugs."
        )
        return []

    _render_ranked_events(ranked_events)

    while True:
        response = console.input(
            "Enter event numbers separated by commas (press Enter for all recommended, or type 'all'): "
        ).strip()
        if not response or response.lower() == "all":
            return events
        try:
            indices = [int(part.strip()) for part in response.split(",") if part.strip()]
        except ValueError:
            console.print("[red]Invalid input.[/red] Please enter numbers separated by commas.")
            continue
        selected: List[EventDetail] = []
        for idx in indices:
            if 1 <= idx <= len(events):
                selected.append(events[idx - 1])
            else:
                console.print(f"[yellow]Ignoring out-of-range index:[/yellow] {idx}")
        if selected:
            return selected
        console.print("No valid selections made. Try again or press Enter for all.")


def run(
    slug: str = "devconnect",
    interactive: bool = True,
    request_delay: float = 1.0,
    preferences: Optional[EventPreferences] = None,
    select_all: bool = False,
    selected_slugs: Optional[List[str]] = None,
    mode: str = "ai",
    headless: bool = True,
    manual_pause: bool = False,
    random_fill: bool = False,
    api_key: Optional[str] = None,
    top_n: int = 10,
    threshold: float = 0.0,
) -> None:
    console.print(f"Loading profile from [bold]data/profile.json[/bold] (will be created if missing).")
    profile = UserProfile.load_or_create()
    client = LumaClient(request_delay=request_delay)
    console.print(f"\nFetching events from Luma calendar: [bold]{slug}[/bold]...")

    with console.status("[bold green]Scraping events from Luma..."):
        events = client.fetch_events_with_details(slug)

    if not events:
        console.print("No events found on the specified calendar.")
        return

    # Filter by preferences first
    filtered = events
    if preferences:
        filtered = [event for event in events if preferences.matches(event)]
        console.print(
            f"Filtered down to {len(filtered)} events using CLI preferences (out of {len(events)} fetched)."
        )
    else:
        console.print(f"Fetched {len(filtered)} events.")

    if not filtered:
        console.print("No events remain after filtering. Adjust your CLI filters and try again.")
        return

    # AI mode: rank events and use AI for matching
    ai_client = None
    if mode == "ai":
        try:
            from .ai_client import AIClient
            from .ranking import filter_by_threshold, get_top_events, rank_events

            console.print("\n[bold cyan]Initializing AI agent...[/bold cyan]")
            ai_client = AIClient(api_key=api_key)

            console.print("Analyzing events with AI to find the best matches for your profile...")
            with console.status("[bold green]AI is ranking events by relevance..."):
                ranked_events = rank_events(filtered, profile, ai_client)

            if not ranked_events:
                console.print("[yellow]No free events found after AI filtering.[/yellow]")
                return

            # Apply threshold filter
            if threshold > 0:
                ranked_events = filter_by_threshold(ranked_events, threshold)
                console.print(f"Filtered to {len(ranked_events)} events with score >= {threshold:.0%}")

            # Apply top-n limit
            if top_n > 0:
                ranked_events = get_top_events(ranked_events, top_n)
                console.print(f"Showing top {len(ranked_events)} ranked events:")

            chosen_events = _select_from_ranked(
                ranked_events,
                interactive=interactive,
                select_all=select_all,
                chosen_slugs=selected_slugs,
            )

        except ValueError as exc:
            console.print(f"[red]AI mode error:[/red] {exc}")
            console.print("Falling back to deterministic mode. Set ANTHROPIC_API_KEY or use --api-key.")
            mode = "deterministic"
            ai_client = None
            chosen_events = _select_events(
                filtered, interactive=interactive, select_all=select_all, chosen_slugs=selected_slugs
            )
        except ImportError as exc:
            console.print(f"[red]Missing dependency:[/red] {exc}")
            console.print("Install anthropic: pip install anthropic")
            mode = "deterministic"
            ai_client = None
            chosen_events = _select_events(
                filtered, interactive=interactive, select_all=select_all, chosen_slugs=selected_slugs
            )
    else:
        # Deterministic mode: no AI ranking
        chosen_events = _select_events(
            filtered, interactive=interactive, select_all=select_all, chosen_slugs=selected_slugs
        )

    if not chosen_events:
        console.print("No events selected. Exiting.")
        return

    # Build application plans
    plans: List[ApplicationPlan] = []

    if ai_client:
        # Use AI for question matching
        from .matcher import match_questions_to_profile

        console.print("\n[bold cyan]AI is matching form questions to your profile...[/bold cyan]")

        for event in chosen_events:
            with console.status(f"[bold green]Processing {event.name}..."):
                matches = match_questions_to_profile(
                    event.registration_questions,
                    profile,
                    ai_client,
                    event_name=event.name,
                    event_description=event.description or "",
                )

                # Convert matches to ApplicationAnswers
                answers: List[ApplicationAnswer] = []
                missing: List[ApplicationAnswer] = []

                for match in matches:
                    # Find the original question to get required status
                    original_q = next(
                        (q for q in event.registration_questions if q.id == match.question_id),
                        None,
                    )
                    required = original_q.required if original_q else False

                    answer = ApplicationAnswer(
                        question_id=match.question_id,
                        label=match.question_label,
                        required=required,
                        answer=match.value,
                        question_type=original_q.question_type if original_q else "text",
                        source_field=match.source,
                    )
                    answers.append(answer)
                    if required and not match.value:
                        missing.append(answer)

                plan = ApplicationPlan(
                    event=event,
                    answers=answers,
                    missing_required=missing,
                    autofill_score=_compute_autofill_score(event, missing),
                )
                plans.append(plan)
    else:
        # Deterministic mode: use original profile matching
        for event in chosen_events:
            answers, missing = profile.build_application_answers(event, interactive=interactive)
            plan = ApplicationPlan(
                event=event,
                answers=answers,
                missing_required=missing,
                autofill_score=_compute_autofill_score(event, missing),
            )
            plans.append(plan)

    plans.sort(key=lambda plan: plan.event.start_local)
    _render_overview(plans)
    _render_itinerary(plans)
    console.print("\nApplication details per event:")
    for plan in plans:
        _render_application_details(plan)

    if mode == "playwright":
        console.print("\nAttempting automated submission via Playwright...")
        try:
            results = submit_with_playwright(
                plans,
                profile,
                headless=headless,
                manual_pause=manual_pause,
                random_fill=random_fill,
            )
        except RuntimeError as exc:
            console.print(f"[red]Automation aborted:[/red] {exc}")
        else:
            render_submission_summary(results)
