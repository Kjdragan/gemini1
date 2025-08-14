from __future__ import annotations

import json
import sqlite3
import requests
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
            handle TEXT,
            lang TEXT,
            created_at TEXT,
            reply_to TEXT,
            root_uri TEXT,
            rev TEXT,
            operation TEXT,
            cid TEXT,
            embed TEXT,
            facets TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts
        USING fts5(text, author, handle, uri UNINDEXED, content='', tokenize='porter');
        CREATE INDEX IF NOT EXISTS idx_posts_root_uri ON posts(root_uri);
        CREATE INDEX IF NOT EXISTS idx_posts_lang ON posts(lang);
        CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author);
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
        con.executescript("""
            DELETE FROM posts;
            INSERT INTO posts_fts(posts_fts) VALUES('delete-all');
        """)
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
                "rev": obj.get("rev"),
                "operation": obj.get("operation"),
                "cid": obj.get("cid"),
                "embed": obj.get("embed"),
                "facets": obj.get("facets"),
            }
            parents[uri] = r["reply_to"]
            rows.append(r)

    memo: Dict[str, str] = {}
    to_insert: List[Tuple] = []
    for r in rows:
        root = _root_for(r["uri"], r["reply_to"], parents, memo)
        to_insert.append((r["uri"], r["text"], r["author"], r["lang"], r["created_at"], r["reply_to"], root, None, r["rev"], r["operation"], r["cid"], r["embed"], r["facets"]))

    with con:
        con.executemany(
            "INSERT OR IGNORE INTO posts (uri, text, author, lang, created_at, reply_to, root_uri, handle, rev, operation, cid, embed, facets) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            to_insert,
        )
        con.execute(
            "INSERT INTO posts_fts (rowid, text, author, handle, uri) SELECT id, text, author, handle, uri FROM posts"
        )

    return con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

def threads_by_topic(
    con: sqlite3.connection,
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

def get_handle_and_update_db(con: sqlite3.Connection, did: str) -> Optional[str]:
    """
    Fetches a user's handle from the Bluesky API using their DID and updates the database.

    Args:
        con: The database connection.
        did: The user's DID.

    Returns:
        The user's handle if found, otherwise None.
    """
    try:
        response = requests.get(
            "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile",
            params={"actor": did},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        handle = data.get("handle")
        if handle:
            with con:
                con.execute(
                    "UPDATE posts SET handle = ? WHERE author = ?", (handle, did)
                )
                # Also update the FTS table
                con.execute(
                    """
                    INSERT INTO posts_fts(posts_fts, rowid, text, author, handle, uri)
                    SELECT 'rebuild', id, text, author, handle, uri
                    FROM posts WHERE author = ?
                    """,
                    (did,),
                )
            return handle
    except requests.RequestException as e:
        print(f"Error fetching handle for {did}: {e}")
    return None
