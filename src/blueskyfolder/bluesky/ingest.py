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

    did = msg.get("did")
    rkey = commit.get("rkey")
    record = commit.get("record") or {}

    text = record.get("text")
    if not isinstance(text, str):
        return None

    operation = commit.get("operation")
    if operation not in ["create", "update"]:
        return None

    langs = record.get("langs")
    if not langs or "en" not in langs:
        return None

    reply = record.get("reply") or {}
    if reply:
        return None

    uri = f"at://{did}/app.bsky.feed.post/{rkey}"

    lang = "en"

    created_at = record.get("createdAt") or datetime.now(timezone.utc).isoformat()

    return {
        "uri": uri,
        "text": text,
        "author": did,
        "lang": lang,
        "created_at": created_at,
        "reply_to": None,
        "rev": commit.get("rev"),
        "operation": commit.get("operation"),
        "cid": commit.get("cid"),
        "embed": json.dumps(record.get("embed")),
        "facets": json.dumps(record.get("facets")),
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
