# Nezuko Luma Agent

This project provides an interactive assistant that prepares your application workflow for cryptocurrency events hosted on Luma (e.g. the Devconnect calendar).

## Features
- Captures and stores your personal profile once, then reuses it for all applications
- Scrapes Luma event listings, fetches detailed registration requirements, and detects application type (instant RSVP, approval, or paid)
- Prompts for your event preferences (keywords, pricing, dates) and filters the calendar accordingly
- Generates a day-by-day itinerary and prints the required fields for each event with suggested answers
- Highlights any missing information so you know what to add before applying

## Getting Started

1. Create and activate the virtual environment (already prepared in `.venv`):
   ```bash
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the agent:
   ```bash
   python main.py
   ```
   - On first run you will be asked to provide your base profile (name, email, wallet, etc.). The information is saved to `data/profile.json`.
   - The agent fetches all events, displays them in a table, and lets you pick specific ones (or press Enter to include them all).
   - Once selected, the agent builds an itinerary and lists every registration question with the answers it can fill in for you.

## CLI options

```bash
python main.py --help
```

Key flags:
- `--slug`: choose another Luma calendar (defaults to `devconnect`).
- `--keywords`: list of terms to filter events before selection, e.g. `--keywords staking infra`.
- `--include-paid`: include events with paid tickets.
- `--exclude-full`: skip application-heavy events that need manual approval.
- `--start-date` / `--end-date`: restrict results to a date range (YYYY-MM-DD).
- `--select-all`: skip the selection prompt and include every fetched event.
- `--events`: provide event slugs to pre-select specific entries.
- `--non-interactive`: suppress prompts for missing answers and just report them (combine with `--select-all` or `--events`).
- `--mode {deterministic,openai}`: choose between the built-in deterministic agent or an (optional) OpenAI-backed mode. The OpenAI workflow currently requires installing the `openai` package and setting `OPENAI_API_KEY`; otherwise the agent falls back to the deterministic path.

## Notes
- The agent currently loads up to the events returned on the calendar landing page. If Luma adds pagination this can be extended in `agent/luma.py`.
- Newly entered answers for custom questions are stored back into `data/profile.json` so you only have to provide them once.
- Be mindful when sharing the generated profile file; it contains sensitive application data.
