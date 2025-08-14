from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import logfire
import pydantic_ai
from dotenv import load_dotenv

from .config import DB_PATH
from .index import connect, ensure_schema, threads_by_topic, get_handle_and_update_db

load_dotenv()


@dataclass
class Deps:
    db_path: Path


agent = pydantic_ai.Agent(
    # If your installed pydantic-ai doesn't recognize 2.5 yet, change to gemini-2.0-flash
    "google-gla:gemini-2.5-flash",
    deps_type=Deps,
    output_type=str,
    system_prompt=(
        "You are a monitoring agent for ATProto/Bluesky. "
        "When asked about a topic, call the tool to fetch complete threads, then synthesize a concise analysis: "
        "themes, sentiments, and notable quotes. Use terse bullets and include 1–2 brief quotes per thread. "
        "The author field contains the user's Decentralized Identifier (did)."
    ),
)


@agent.tool
def filter_threads_by_topic(
    ctx: pydantic_ai.RunContext[Deps],
    topic: str,
    limit: int = 10,
    preferred_langs: Optional[List[str]] = None,
) -> List[str]:
    con = connect(ctx.deps.db_path)
    ensure_schema(con)
    threads = threads_by_topic(
        con, topic=topic, limit_threads=limit, preferred_langs=preferred_langs
    )
    rendered: List[str] = []
    for thread in threads[:limit]:
        lines = []
        for r in thread:
            ts = (r["created_at"] or "")[:19].replace("T", " ")
            author = r["author"] or "unknown"
            text = (r["text"] or "").replace("\n", " ")
            lines.append(f"[{ts}] {author}: {text}")
        rendered.append("\n".join(lines))
    return rendered


@agent.tool
def get_user_profile_by_did(
    ctx: pydantic_ai.RunContext[Deps],
    did: str,
) -> str:
    """
    Retrieves a user's profile information (handle) by their DID and stores it in the database.

    Args:
        did: The user's Decentralized Identifier (DID).
    """
    con = connect(ctx.deps.db_path)
    ensure_schema(con)
    handle = get_handle_and_update_db(con, did=did)
    if handle:
        return f"Successfully found and stored handle ''{handle}'' for DID ''{did}''_"
    return f"Could not find a handle for DID ''{did}'' _"


def run_cli(db_path: Path, topic_hint: Optional[str] = None) -> None:
    # Configure Logfire (optional)
    logfire.configure(console=False)
    logfire.instrument_pydantic_ai()

    deps = Deps(db_path=db_path)

    print("\n--- Bluesky Firehose Agent ---")
    print("Type your questions or 'quit' to exit.")
    if topic_hint:
        print(f"(hint: try topic like: {topic_hint!r})")
    print("-" * 40)

    history = []
    while True:
        try:
            q = input("> ").strip()
            if q.lower() in {"q", "quit", "exit"}:
                print("Goodbye!")
                break
            if not q:
                continue
            res = agent.run_sync(q, deps=deps, message_history=history)
            print(f"\nAgent:\n{res.output}\n")
            history.extend(res.new_messages())
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:
            print("Error:", e, file=sys.stderr)

def main() -> None:
    """CLI entrypoint for running the agent against an existing DB."""
    run_cli(db_path=DB_PATH)


if __name__ == "__main__":
    main()
