#!/usr/bin/env python3
"""
Assign owner to existing conversations.

Usage examples:
  python3 scripts/migrate_conversations_assign_user.py --username alice
  python3 scripts/migrate_conversations_assign_user.py --username alice --only-empty  # default
  python3 scripts/migrate_conversations_assign_user.py --username alice --conversations data/conversations.json --dry-run

Notes:
  - Creates a timestamped backup next to the conversations file.
  - By default updates only conversations with missing/empty/anonymous `user`.
  - Restart the backend after running to load updates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def load_conversations(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Conversations file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_conversations(path: Path, data: Dict[str, Any]):
    backup = path.with_name(
        path.stem + "_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + path.suffix
    )
    backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # After backup, write the new data to original file
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_owner(
    data: Dict[str, Any], username: str, only_empty: bool = True
) -> tuple[int, int]:
    total = 0
    changed = 0
    for conv_id, conv in data.items():
        total += 1
        owner = conv.get("user")
        should_update = not only_empty or (owner in (None, "", "anonymous") or "user" not in conv)
        if should_update:
            conv["user"] = username
            changed += 1
    return total, changed


def main():
    ap = argparse.ArgumentParser(description="Assign owner to conversations")
    ap.add_argument("--username", required=True, help="Target username to assign")
    ap.add_argument(
        "--conversations",
        default="data/conversations.json",
        help="Path to conversations.json",
    )
    ap.add_argument(
        "--only-empty",
        action="store_true",
        default=True,
        help="Only update conversations missing a user (default)",
    )
    ap.add_argument("--all", dest="only_empty", action="store_false", help="Update all conversations to this user")
    ap.add_argument("--dry-run", action="store_true", help="Preview without writing changes")
    args = ap.parse_args()

    path = Path(args.conversations)
    data = load_conversations(path)

    total, changed = migrate_owner(data, args.username, only_empty=args.only_empty)

    print(f"[MIGRATE] conversations: {total}, to_change: {changed}, user= {args.username}")
    if args.dry_run:
        print("[MIGRATE] dry-run only; no files written.")
        return

    # Save with backup
    save_conversations(path, data)
    print(f"[MIGRATE] done. Backup written, file updated: {path}")


if __name__ == "__main__":
    main()

