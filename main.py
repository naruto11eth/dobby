from __future__ import annotations

import argparse

from agent.cli import run
from agent.preferences import EventPreferences, parse_date_str


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI agent for preparing applications to Luma-hosted crypto events.")
    parser.add_argument("--slug", default="devconnect", help="Luma calendar slug to source events from.")
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
        choices=["deterministic", "openai"],
        default="deterministic",
        help="Choose between the built-in deterministic agent or an optional OpenAI-powered mode.",
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


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    preferences = build_preferences_from_args(args)
    run(
        slug=args.slug,
        interactive=not args.non_interactive,
        request_delay=args.delay,
        preferences=preferences,
        select_all=args.select_all,
        selected_slugs=args.events,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
