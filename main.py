from __future__ import annotations

import argparse

from agent.cli import run
from agent.preferences import EventPreferences, parse_date_str


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI agent for preparing applications to Luma-hosted crypto events.")
    parser.add_argument("--slug", default=None, help="Luma calendar slug to source events from (e.g., 'ethdenver2025' or full URL).")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt for missing answers; report them instead.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay between HTTP requests to avoid overwhelming Luma (seconds).",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        help="Filter events by keywords (matches name, description, host, categories).",
    )
    parser.add_argument(
        "--include-paid",
        action="store_true",
        help="Allow paid events in the results.",
    )
    parser.add_argument(
        "--exclude-full",
        action="store_true",
        help="Exclude events that require lengthier application workflows.",
    )
    parser.add_argument("--start-date", help="Earliest event date to include (YYYY-MM-DD).")
    parser.add_argument("--end-date", help="Latest event date to include (YYYY-MM-DD).")
    parser.add_argument(
        "--select-all",
        action="store_true",
        help="Skip the selection prompt and include all fetched events.",
    )
    parser.add_argument(
        "--events",
        nargs="*",
        help="Specify event slugs to include (bypasses the selection prompt).",
    )
    parser.add_argument(
        "--mode",
        choices=["deterministic", "ai", "playwright"],
        default="ai",
        help="Agent mode: deterministic (rule-based), ai (Claude ranking), or playwright (ai + browser automation).",
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top-ranked events to display (default: 10).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="Minimum combined score to include an event (0.0-1.0).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run Playwright in headless mode (default: True).",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run Playwright with visible browser window.",
    )
    parser.add_argument(
        "--manual-pause",
        action="store_true",
        help="Pause before final form submission for manual review.",
    )
    parser.add_argument(
        "--random-fill",
        action="store_true",
        help="Fill missing required fields with placeholder values.",
    )
    return parser


def build_preferences_from_args(args: argparse.Namespace) -> EventPreferences | None:
    has_filters = any(
        [
            args.keywords,
            args.include_paid,
            args.exclude_full,
            args.start_date,
            args.end_date,
        ]
    )
    if not has_filters:
        return None
    return EventPreferences(
        keywords=args.keywords or [],
        include_paid=args.include_paid,
        include_full_applications=not args.exclude_full,
        start_date=parse_date_str(args.start_date) if args.start_date else None,
        end_date=parse_date_str(args.end_date) if args.end_date else None,
    )


def extract_slug_from_url(url_or_slug: str) -> str:
    """Extract calendar slug from Luma URL or return as-is if already a slug."""
    url_or_slug = url_or_slug.strip()
    # Handle full URLs like https://lu.ma/ethdenver2025 or https://luma.com/ethdenver2025
    if "lu.ma/" in url_or_slug:
        return url_or_slug.split("lu.ma/")[-1].split("?")[0].strip("/")
    if "luma.com/" in url_or_slug:
        return url_or_slug.split("luma.com/")[-1].split("?")[0].strip("/")
    return url_or_slug


def prompt_for_calendar() -> str:
    """Interactively prompt user for Luma calendar URL or slug."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Dobby[/bold cyan] - AI-Powered Luma Event Registration Agent\n\n"
        "Automatically register for crypto events using AI to:\n"
        "  - Rank events by relevance to your profile\n"
        "  - Fill registration forms intelligently\n"
        "  - Generate personalized answers for open-ended questions",
        title="Welcome",
        border_style="cyan",
    ))
    console.print()

    console.print("[bold]How to find a Luma calendar:[/bold]")
    console.print("  1. Go to [link=https://lu.ma]lu.ma[/link] and find an event series or calendar")
    console.print("  2. Copy the URL (e.g., https://lu.ma/ethdenver2025)")
    console.print("  3. Paste it below")
    console.print()

    console.print("[dim]Examples:[/dim]")
    console.print("  - https://lu.ma/ethdenver2025")
    console.print("  - https://lu.ma/devconnect")
    console.print("  - ethdenver2025 (just the slug)")
    console.print()

    while True:
        response = console.input("[bold green]Enter Luma calendar URL or slug:[/bold green] ").strip()
        if response:
            return extract_slug_from_url(response)
        console.print("[yellow]Please enter a valid Luma calendar URL or slug.[/yellow]")


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    # Prompt for calendar slug if not provided
    slug = args.slug
    if not slug and not args.non_interactive:
        slug = prompt_for_calendar()
    elif not slug:
        print("Error: --slug is required in non-interactive mode.")
        print("Example: python main.py --slug ethdenver2025 --non-interactive")
        return

    preferences = build_preferences_from_args(args)
    headless = not args.no_headless
    run(
        slug=slug,
        interactive=not args.non_interactive,
        request_delay=args.delay,
        preferences=preferences,
        select_all=args.select_all,
        selected_slugs=args.events,
        mode=args.mode,
        headless=headless,
        manual_pause=args.manual_pause,
        random_fill=args.random_fill,
        api_key=args.api_key,
        top_n=args.top_n,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
