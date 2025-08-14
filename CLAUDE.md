# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two main Python applications focused on ATProto/Bluesky firehose analysis:

1. **Bluesky Agent** (`src/blueskyfolder/`): A CLI agent using Pydantic AI + Google Gemini to analyze Bluesky/ATProto firehose data
2. **Samuel** (`samuel/`): MCP (Model Context Protocol) demonstration project with Pydantic AI

## Development Commands

### Setup
```bash
# Install the main package (editable)
pip install -e .

# Install the bluesky subpackage (editable)  
pip install -e ./src/blueskyfolder/
```

### Running Applications

**Bluesky firehose capture and analysis:**
```bash
# Run full pipeline: capture → index → CLI agent
bsky-capture-and-run --capture 30 --topic "example"

# Run just the agent CLI (requires existing DB)
bsky

# Run as module without install
python -m blueskyfolder.bluesky.main
```

**Individual components:**
```bash
# Basic entry point
python main.py

# Bluesky module directly
python -m blueskyfolder.bluesky.agent_cli
```

## Architecture

### Core Dependencies
- **Pydantic AI**: Agent framework with tool calling
- **Google Gemini**: LLM backend (specifically `google-gla:gemini-2.5-flash`)
- **Logfire**: Observability and tracing
- **WebSockets**: ATProto firehose connection

### Key Components

**Firehose Processing Pipeline:**
1. `ingest.py`: Captures live ATProto firehose via WebSocket → JSONL
2. `index.py`: Processes JSONL → SQLite database with thread reconstruction  
3. `agent_cli.py`: Interactive agent that queries the database

**Agent Architecture:**
- `AgentDependencies`/`Deps`: Dependency injection pattern for state
- Tools: `filter_threads_by_topic()` - retrieves conversation threads by topic
- System prompt: Configured for ATProto/Bluesky monitoring and analysis

### File Structure
```
src/blueskyfolder/bluesky/
├── main.py           # Standalone CLI demo
├── agent_cli.py      # Full database-backed agent
├── config.py         # Paths and constants  
├── ingest.py         # Firehose capture
└── index.py          # Database operations
```

## Environment Variables
- `GOOGLE_API_KEY`: Required for Gemini API access
- `LOGFIRE_API_KEY`: Optional for remote tracing (defaults to local-only)

## Entry Points
- `bsky-capture-and-run`: Full pipeline (capture → index → CLI)
- `bsky`: Agent CLI only (requires existing database)

## Data Flow
WebSocket (Jetstream) → JSONL file → SQLite database → Agent tools → Natural language analysis