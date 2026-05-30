#!/usr/bin/env python3
"""Next available Supabase migration ID.

Usage:
    python scripts/migration_next_id.py                  → 083
    python scripts/migration_next_id.py add_feature      → 083_add_feature.sql
    python scripts/migration_next_id.py --template add_x → 083_add_x.sql

Options:
    --dir PATH   Override migrations directory (default: supabase/migrations/)
"""

import re
import sys
from pathlib import Path

_DEFAULT_MIGS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"


def max_num(migs_dir: Path) -> int:
    """Return the highest NNN prefix found in migs_dir, or 0 if none."""
    top = 0
    for f in migs_dir.iterdir():
        m = re.match(r"^(\d{3})_", f.name)
        if m:
            top = max(top, int(m.group(1)))
    return top


def next_num(migs_dir: Path) -> int:
    return max_num(migs_dir) + 1


if __name__ == "__main__":
    args = sys.argv[1:]

    migs_dir = _DEFAULT_MIGS
    if "--dir" in args:
        idx = args.index("--dir")
        migs_dir = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if not migs_dir.exists():
        sys.exit(f"error: migrations dir not found: {migs_dir}")

    nid = next_num(migs_dir)

    # Strip leading --template flag (alias, kept for backwards compat)
    if args and args[0] == "--template":
        args = args[1:]

    if args:
        slug = args[0].lstrip("_")
        print(f"{nid:03d}_{slug}.sql")
    else:
        print(f"{nid:03d}")
