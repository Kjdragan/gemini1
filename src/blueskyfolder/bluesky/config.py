from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]     # /home/kjdrag/lrepos/gemini1
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_CAPTURE = ROOT / "firehose_capture.jsonl"
DB_PATH = DATA_DIR / "firehose.db"

# Jetstream public firehose (community endpoint)
JETSTREAM_WS = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
