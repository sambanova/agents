"""Remove credential-like keys from stored LangGraph checkpoint metadata.

Dry run by default; pass --apply to write changes.

    REDIS_URL=redis://:<password>@<host>:6379/0 \
        python scripts/scrub_checkpoint_metadata.py [--apply]
"""

import argparse
import json
import os

import redis

from agents.storage.checkpoint_serde import strip_sensitive_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    client = redis.Redis.from_url(os.environ["REDIS_URL"])
    scanned = affected = 0
    for key in client.scan_iter(match="checkpoint:*", count=1000):
        scanned += 1
        raw = client.execute_command("JSON.GET", key, "$.metadata")
        if not raw:
            continue
        values = json.loads(raw)
        if not values:
            continue
        stored = values[0]
        metadata = json.loads(stored) if isinstance(stored, str) else stored
        if not isinstance(metadata, dict):
            continue
        cleaned = strip_sensitive_metadata(metadata)
        if cleaned == metadata:
            continue
        affected += 1
        if args.apply:
            new_value = json.dumps(cleaned) if isinstance(stored, str) else cleaned
            client.execute_command("JSON.SET", key, "$.metadata", json.dumps(new_value))

    action = "updated" if args.apply else "would update"
    print(f"scanned {scanned} checkpoints, {action} {affected}")


if __name__ == "__main__":
    main()
