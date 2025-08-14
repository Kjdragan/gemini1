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
