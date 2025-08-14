# Bluesky Agent (Pydantic AI + Gemini + Logfire)

CLI application that uses Pydantic AI with Google's Gemini to analyze a simulated ATProto Firehose.

## Features
- Agent configured with model `google-gla:gemini-2.0-flash`
- Example tool: `filter_threads_by_topic`
- Logfire instrumentation for observability

## Requirements
- Python 3.13+
- Environment variables:
  - `GOOGLE_API_KEY` — Gemini API key (from Google AI Studio)
  - Optional: `LOGFIRE_API_KEY` — to send traces to Logfire (otherwise local-only)

Copy `.env.example` to `.env` and fill your keys:

```bash
cp bluesky/.env.example bluesky/.env
```

## Install & Run

### Option A: Standard virtualenv + pip
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ./bluesky
# Run the CLI
bluesky
```

### Option B: Run as a module without install
```bash
python -m bluesky.main
```

## Development
- Entry point: `bluesky.main:main`
- Package: `bluesky/`
- Adjust `system_prompt` and tools in `bluesky/main.py`.
