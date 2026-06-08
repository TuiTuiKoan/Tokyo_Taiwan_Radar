#!/usr/bin/env python3
"""
i18n parity checker — shared by pre-commit, pre-push hooks and CI.

Modes:
  --staged                 Compare staged files vs HEAD (pre-commit use)
  --range BASE..HEAD       Compare key counts across a git range (pre-push / CI use)

Exit codes:
  0  All checks passed
  1  Key regression detected or three-locale parity mismatch
"""
import argparse, json, subprocess, sys
from pathlib import Path

LOCALE_FILES = ["web/messages/zh.json", "web/messages/en.json", "web/messages/ja.json"]
REPO_ROOT = Path(__file__).parent.parent  # scripts/ -> repo root


def flatten_keys(d: dict, prefix: str = "") -> set:
    keys = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= flatten_keys(v, full)
        else:
            keys.add(full)
    return keys


def load_keys_from_blob(git_ref: str, filepath: str):
    result = subprocess.run(
        ["git", "show", f"{git_ref}:{filepath}"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        return None
    try:
        return flatten_keys(json.loads(result.stdout))
    except json.JSONDecodeError:
        return None


def load_keys_from_index(filepath: str):
    result = subprocess.run(
        ["git", "show", f":0:{filepath}"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        return None
    try:
        return flatten_keys(json.loads(result.stdout))
    except json.JSONDecodeError:
        return None


def check_staged() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    staged_files = [f for f in result.stdout.splitlines() if f in LOCALE_FILES]

    if not staged_files:
        return 0

    failed = False
    for filepath in staged_files:
        head_keys = load_keys_from_blob("HEAD", filepath)
        staged_keys = load_keys_from_index(filepath)

        if head_keys is None or staged_keys is None:
            continue

        removed = head_keys - staged_keys
        if removed:
            print(f"\npre-commit: i18n regression detected — commit blocked!")
            print(f"  File: {filepath}")
            print(f"  Keys removed ({len(removed)} total): {sorted(removed)[:5]}{'...' if len(removed) > 5 else ''}")
            print(f"\n  HEAD had {len(head_keys)} keys, staged has {len(staged_keys)} keys.")
            print(f"  To bypass (use with caution): git commit --no-verify")
            failed = True

    if not failed:
        all_current = {}
        for filepath in LOCALE_FILES:
            keys = load_keys_from_index(filepath) or load_keys_from_blob("HEAD", filepath)
            if keys is not None:
                all_current[filepath] = keys

        if len(all_current) == 3:
            key_sets = list(all_current.values())
            if not (key_sets[0] == key_sets[1] == key_sets[2]):
                zh = all_current.get(LOCALE_FILES[0], set())
                en = all_current.get(LOCALE_FILES[1], set())
                ja = all_current.get(LOCALE_FILES[2], set())
                print("\npre-commit: i18n three-locale parity mismatch — commit blocked!")
                if zh - en: print(f"  zh has {len(zh-en)} keys missing in en: {sorted(zh-en)[:3]}")
                if en - zh: print(f"  en has {len(en-zh)} keys missing in zh: {sorted(en-zh)[:3]}")
                if zh - ja: print(f"  zh has {len(zh-ja)} keys missing in ja: {sorted(zh-ja)[:3]}")
                failed = True

    return 1 if failed else 0


def check_range(git_range: str) -> int:
    if ".." not in git_range:
        print(f"Error: --range requires BASE..HEAD format, got: {git_range}")
        return 1

    base_ref, head_ref = git_range.split("..", 1)
    if not base_ref or not head_ref:
        print(f"Error: Invalid range: {git_range}")
        return 1

    failed = False
    all_base = {}
    all_head = {}

    for filepath in LOCALE_FILES:
        base_keys = load_keys_from_blob(base_ref, filepath)
        head_keys = load_keys_from_blob(head_ref, filepath)

        if base_keys is None or head_keys is None:
            continue

        all_base[filepath] = base_keys
        all_head[filepath] = head_keys

        removed = base_keys - head_keys
        if removed:
            print(f"\ni18n regression detected in range {git_range}:")
            print(f"  File: {filepath}")
            print(f"  Keys removed ({len(removed)} total): {sorted(removed)[:5]}{'...' if len(removed) > 5 else ''}")
            print(f"  Base had {len(base_keys)} keys, head has {len(head_keys)} keys.")
            failed = True

    if len(all_head) == 3:
        key_sets = list(all_head.values())
        if not (key_sets[0] == key_sets[1] == key_sets[2]):
            print(f"\ni18n three-locale parity mismatch at {head_ref}:")
            zh = all_head.get(LOCALE_FILES[0], set())
            en = all_head.get(LOCALE_FILES[1], set())
            ja = all_head.get(LOCALE_FILES[2], set())
            if zh - en: print(f"  zh has {len(zh-en)} extra keys vs en: {sorted(zh-en)[:3]}")
            if en - zh: print(f"  en has {len(en-zh)} extra keys vs zh: {sorted(en-zh)[:3]}")
            if zh - ja: print(f"  zh has {len(zh-ja)} extra keys vs ja: {sorted(zh-ja)[:3]}")
            failed = True

    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description="i18n parity checker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="Check staged files vs HEAD")
    group.add_argument("--range", dest="git_range", metavar="BASE..HEAD",
                       help="Check key counts across git range")
    args = parser.parse_args()

    if args.staged:
        sys.exit(check_staged())
    else:
        sys.exit(check_range(args.git_range))


if __name__ == "__main__":
    main()
