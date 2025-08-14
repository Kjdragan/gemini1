Got it. Here’s a clean, modular mini-app that:

Captures ~30s of the Bluesky (ATProto) public firehose (Jetstream) into NDJSON

Indexes it into SQLite + FTS5

Runs a Pydantic-AI + Gemini CLI agent that can filter full threads by topic and summarize

You’ll get separate files you can drop into your repo. After that, you can run:

# (1) capture ~30 seconds, build index, and launch the CLI
uv run -s bsky-capture-and-run

# (2) later, just launch the CLI using the existing index
uv run -s bsky

Directory layout
/home/kjdrag/lrepos/gemini1/
├─ pyproject.toml                  # add scripts block below
├─ .env                            # put GOOGLE_API_KEY=... here (or GEMINI_API_KEY)
├─ data/
│   └─ (created automatically)
├─ blueskyfolder/
│  ├─ __init__.py
│  ├─ __main__.py                  # entry -> capture (optional) -> index -> agent
│  └─ bluesky/
│     ├─ __init__.py
│     ├─ config.py                 # paths/constants
│     ├─ ingest.py                 # 30-second Jetstream capture -> NDJSON
│     ├─ index.py                  # SQLite+FTS5 index & queries
│     └─ agent_cli.py              # Pydantic-AI agent + CLI loop

1) blueskyfolder/__init__.py
# empty, just marks package

2) blueskyfolder/__main__.py
from __future__ import annotations

import sys
from pathlib import Path

from blueskyfolder.bluesky.config import ROOT, DEFAULT_CAPTURE, DB_PATH
from blueskyfolder.bluesky import ingest, index, agent_cli


def main() -> None:
    # tiny arg parser:
    #   --capture [seconds]  (default 30)
    #   --out <path.ndjson>  (default ROOT / "firehose_capture.jsonl")
    #   --topic <string>     (optional, just a hint you can pass to the CLI prompt)
    argv = sys.argv[1:]
    seconds = 30
    out_path = DEFAULT_CAPTURE
    topic_hint = None

    it = iter(argv)
    for a in it:
        if a == "--capture":
            try:
                seconds = int(next(it))
            except StopIteration:
                raise SystemExit("--capture requires an integer seconds value")
        elif a == "--out":
            try:
                out_path = Path(next(it)).expanduser().resolve()
            except StopIteration:
                raise SystemExit("--out requires a path")
        elif a == "--topic":
            try:
                topic_hint = next(it)
            except StopIteration:
                raise SystemExit("--topic requires a string")
        else:
            print(f"Unknown arg: {a}", file=sys.stderr)
            raise SystemExit(2)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) capture
    print(f"[main] capturing ~{seconds}s to {out_path} …")
    ingest.capture_ndjson(seconds=seconds, out_path=out_path)

    # 2) index
    print(f"[main] indexing {out_path} -> {DB_PATH} …")
    con = index.connect(DB_PATH)
    index.ensure_schema(con)
    index.ingest_ndjson(con, out_path)

    # 3) run agent CLI
    agent_cli.run_cli(db_path=DB_PATH, topic_hint=topic_hint)


if __name__ == "__main__":
    main()

3) blueskyfolder/bluesky/__init__.py
# empty, marks package

4) blueskyfolder/bluesky/config.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]     # /home/kjdrag/lrepos/gemini1
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_CAPTURE = ROOT / "firehose_capture.jsonl"
DB_PATH = DATA_DIR / "firehose.db"

# Jetstream public firehose (community endpoint)
JETSTREAM_WS = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"

5) blueskyfolder/bluesky/ingest.py — capture ~30 seconds to NDJSON
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import websockets  # pip install websockets

from .config import JETSTREAM_WS


def _normalize_record(msg: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Parse Jetstream 'commit' message -> normalized post row or None.

    We extract:
      - uri: at://<did>/app.bsky.feed.post/<rkey>
      - text: record['text']
      - author: did
      - lang: first langs[] if provided (lowercased)
      - created_at: record['createdAt'] or now()
      - reply_to: parent at-uri if reply exists
    """
    commit = msg.get("commit")
    if not commit:
        return None
    if commit.get("collection") != "app.bsky.feed.post":
        return None

    did = commit.get("repo")
    rkey = commit.get("rkey")
    record = commit.get("record") or {}

    text = record.get("text")
    if not isinstance(text, str):
        return None

    uri = f"at://{did}/app.bsky.feed.post/{rkey}"

    lang = None
    langs = record.get("langs")
    if isinstance(langs, list) and langs:
        lang = str(langs[0]).lower()

    created_at = record.get("createdAt") or datetime.now(timezone.utc).isoformat()

    reply = record.get("reply") or {}
    reply_parent = reply.get("parent") or {}
    reply_uri = reply_parent.get("uri")  # at-uri of parent post

    return {
        "uri": uri,
        "text": text,
        "author": did,
        "lang": lang,
        "created_at": created_at,
        "reply_to": reply_uri,
    }


async def _capture_async(seconds: int, out_path: Path) -> None:
    count = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[capture] connecting {JETSTREAM_WS}")

    async with websockets.connect(JETSTREAM_WS, max_size=2**23) as ws:
        ws_ping = asyncio.create_task(_pinger(ws))
        try:
            with out_path.open("w", encoding="utf-8") as f:
                stop = asyncio.get_event_loop().time() + max(1, seconds)
                while asyncio.get_event_loop().time() < stop:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    rec = _normalize_record(msg)
                    if not rec:
                        continue
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    count += 1
        finally:
            ws_ping.cancel()

    print(f"[capture] wrote {count} posts to {out_path}")


async def _pinger(ws) -> None:
    try:
        while True:
            await asyncio.sleep(15)
            try:
                await ws.ping()
            except Exception:
                return
    except asyncio.CancelledError:
        return


def capture_ndjson(seconds: int, out_path: Path) -> None:
    """Synchronous wrapper so we can call from __main__ easily."""
    asyncio.run(_capture_async(seconds=seconds, out_path=out_path))

6) blueskyfolder/bluesky/index.py — SQLite + FTS5 index & queries
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            uri TEXT UNIQUE,
            text TEXT,
            author TEXT,
            lang TEXT,
            created_at TEXT,
            reply_to TEXT,
            root_uri TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts
        USING fts5(text, author, uri UNINDEXED, content='', tokenize='porter');
        CREATE INDEX IF NOT EXISTS idx_posts_root_uri ON posts(root_uri);
        CREATE INDEX IF NOT EXISTS idx_posts_lang ON posts(lang);
        """
    )

def _root_for(uri: str, reply_to: Optional[str], parents: Dict[str, Optional[str]], memo: Dict[str, str]) -> str:
    if uri in memo:
        return memo[uri]
    cur = uri
    seen = set()
    while True:
        if cur in memo:
            root = memo[cur]; break
        if cur in seen:
            root = cur; break
        seen.add(cur)
        parent = parents.get(cur)
        if not parent:
            root = cur; break
        cur = parent
    for u in seen:
        memo[u] = root
    return root

def ingest_ndjson(con: sqlite3.Connection, path: Path) -> int:
    ensure_schema(con)
    with con:
        con.executescript("DELETE FROM posts; DELETE FROM posts_fts;")
    parents: Dict[str, Optional[str]] = {}
    rows: List[Dict] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            uri = obj.get("uri")
            if not uri:
                continue
            r = {
                "uri": uri,
                "text": obj.get("text") or "",
                "author": obj.get("author") or "",
                "lang": (obj.get("lang") or None),
                "created_at": obj.get("created_at") or "",
                "reply_to": obj.get("reply_to"),
            }
            parents[uri] = r["reply_to"]
            rows.append(r)

    memo: Dict[str, str] = {}
    to_insert: List[Tuple] = []
    for r in rows:
        root = _root_for(r["uri"], r["reply_to"], parents, memo)
        to_insert.append((r["uri"], r["text"], r["author"], r["lang"], r["created_at"], r["reply_to"], root))

    with con:
        con.executemany(
            "INSERT OR IGNORE INTO posts (uri, text, author, lang, created_at, reply_to, root_uri) VALUES (?, ?, ?, ?, ?, ?, ?)",
            to_insert,
        )
        con.execute(
            "INSERT INTO posts_fts (rowid, text, author, uri) SELECT id, text, author, uri FROM posts"
        )

    return con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

def threads_by_topic(
    con: sqlite3.Connection,
    topic: str,
    limit_threads: int = 10,
    preferred_langs: Optional[List[str]] = None,
):
    ensure_schema(con)
    topic = topic.strip()
    if not topic:
        return []

    lang_clause = ""
    params: List = [topic]
    if preferred_langs:
        placeholders = ",".join(["?"] * len(preferred_langs))
        lang_clause = f" AND p.lang IN ({placeholders})"
        params.extend([l.lower() for l in preferred_langs])

    params.append(limit_threads)

    sql = f"""
        WITH matches AS (
          SELECT p.root_uri
          FROM posts_fts f
          JOIN posts p ON p.id = f.rowid
          WHERE posts_fts MATCH ?
          {lang_clause}
          GROUP BY p.root_uri
          ORDER BY COUNT(*) DESC
          LIMIT ?
        )
        SELECT p.*
        FROM posts p
        JOIN matches m ON m.root_uri = p.root_uri
        ORDER BY p.root_uri, p.created_at
    """
    cur = con.execute(sql, params)
    rows = cur.fetchall()
    grouped = {}
    for r in rows:
        grouped.setdefault(r["root_uri"], []).append(r)
    return list(grouped.values())

7) blueskyfolder/bluesky/agent_cli.py — Pydantic-AI agent + CLI
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import logfire
import pydantic_ai
from dotenv import load_dotenv

from .index import connect, ensure_schema, ingest_ndjson, threads_by_topic

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
        "themes, sentiments, and notable quotes. Use terse bullets and include 1–2 brief quotes per thread."
    ),
)

@agent.tool
def filter_threads_by_topic(
    ctx: pydantic_ai.RunContext[Deps],
    topic: str,
    limit: int = 10,
    preferred_langs: Optional[List[str]] = None
) -> List[str]:
    con = connect(ctx.deps.db_path)
    ensure_schema(con)
    threads = threads_by_topic(con, topic=topic, limit_threads=limit, preferred_langs=preferred_langs)
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

8) pyproject.toml — add scripts (keep your existing content; append below)
[tool.uv.scripts]
# 30s capture -> index -> launch agent CLI
bsky-capture-and-run = "python -m blueskyfolder --capture 30 --topic agents"

# Just run the agent (using whatever is already indexed in data/firehose.db)
bsky = "python -m blueskyfolder.bluesky.agent_cli"


If you prefer a one-word command: uv run -s bsky-capture-and-run

9) Install deps (once)

From the repo root:

uv add pydantic-ai google-genai python-dotenv logfire websockets
# if your pydantic-ai is old and doesn’t recognize 2.5:
# uv add -U pydantic-ai


Add your key to .env (root):

GOOGLE_API_KEY=YOUR_KEY_HERE
# or GEMINI_API_KEY=...

10) Usage
# capture ~30s, index, run CLI
uv run -s bsky-capture-and-run

# later: just run CLI (uses existing index)
uv run -s bsky


Try prompts like:

Show me threads about "agents"

What are people saying about twitter vs bluesky?

Summarize discussions about "openai" in English only

Notes

Short capture: the ingester stops on a wall-clock timer; you’ll get a small, fast DB build that’s perfect for testing.

Threading: we reconstruct roots via reply_to chains and return the entire thread sorted by created_at.

FTS5: substring/porter stemming search on text and author. Quoted phrases work too (e.g., "open source").

Live runs: you can increase --capture 120 later, or capture to a different file with --out ./data/cap.jsonl and re-index.
