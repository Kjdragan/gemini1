# Plan for Resolving Bluesky DIDs to Handles

This document outlines the plan to enhance the Bluesky firehose monitoring application by resolving Decentralized Identifiers (DIDs) to human-readable user handles.

## Goal

The current application displays the author of a post as a `did` (e.g., `did:plc:jmythrcvilqveev4qtxrmucu`). The goal is to display the user's handle (e.g., `@username.bsky.social`) instead.

## Requirements

To achieve this, we will need to make a network request to a Bluesky server for each unique `did` we encounter. This will add a network dependency to our application and will slow down the ingestion process, so it should be implemented as an optional, separate process.

No special developer API key is required for this functionality. The required endpoint is public.

## API Endpoint

The correct endpoint to resolve a `did` to a handle is `com.atproto.identity.resolveHandle`.

*   **URL:** `https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle`
*   **Method:** `GET`
*   **Query Parameter:** `handle=<did>`
*   **Authentication:** Not required.

**Example Request:**

```
GET https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle?handle=did:plc:jmythrcvilqveev4qtxrmucu
```

**Example Response:**

The response will be a JSON object containing the user's handle.

```json
{
  "handle": "bsky.app"
}
```

## Implementation Plan

1.  **Add a new `handles` table to the database:**
    *   This table will store the mapping between `did` and `handle`.
    *   It should have two columns: `did` (TEXT, UNIQUE) and `handle` (TEXT).

2.  **Create a new script for resolving `did`s:**
    *   This script will be separate from the main application logic to avoid slowing down the firehose capture.
    *   It will:
        *   Connect to the database.
        *   Select all unique `did`s from the `posts` table that are not yet in the `handles` table.
        *   For each `did`, make a request to the `resolveHandle` endpoint.
        *   Parse the response and insert the `did` and `handle` into the `handles` table.

3.  **Update the agent to display the handle:**
    *   The `filter_threads_by_topic` tool in `agent_cli.py` will be modified to:
        *   Join the `posts` table with the `handles` table on the `author` (`did`) column.
        *   Display the `handle` if it exists, otherwise display the `did`.

## Example Code (for the resolver script)

```python
import sqlite3
import requests

def resolve_dids(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Ensure handles table exists
    con.execute("""
        CREATE TABLE IF NOT EXISTS handles (
            did TEXT UNIQUE,
            handle TEXT
        )
    """)

    # Find unresolved dids
    cur = con.execute("""
        SELECT DISTINCT author FROM posts
        WHERE author NOT IN (SELECT did FROM handles)
    """)
    dids_to_resolve = [row['author'] for row in cur.fetchall()]

    for did in dids_to_resolve:
        try:
            response = requests.get(
                "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle",
                params={"handle": did}
            )
            response.raise_for_status()
            handle = response.json().get("handle")
            if handle:
                print(f"Resolved {did} to {handle}")
                with con:
                    con.execute("INSERT OR IGNORE INTO handles (did, handle) VALUES (?, ?)", (did, handle))
        except requests.exceptions.RequestException as e:
            print(f"Could not resolve {did}: {e}")

if __name__ == "__main__":
    # Example usage
    resolve_dids("data/firehose.db")
```
