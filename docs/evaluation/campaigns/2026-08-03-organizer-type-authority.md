---
campaign_slug: "2026-08-03-organizer-type-authority"
description: "Process telemetry for campaign 2026-08-03-organizer-type-authority; all metrics recomputable from docs/evaluation/campaigns/ledger/2026-08-03-organizer-type-authority-cd605c950143.jsonl."
generator_blobs:
  ".github/skills/session-analytics/oneoff_campaign_anchor.py": "git-blob-sha1:74f52b7eaf565be80d8db73d9cd6824e06fc8d30"
generator_source_commit: "fe95e6ab5fe1eac73fa03cdc98d21f1f3fb25390"
ledger_digest: "sha256:cd605c95014358722c54bd3b2470bc606c9b43b4e7d6491a43eac833a76cddad"
ledger_path: "docs/evaluation/campaigns/ledger/2026-08-03-organizer-type-authority-cd605c950143.jsonl"
owning_spec_slug: "evaluation-framework"
record_kind: "process_telemetry"
schema_version: 1
title: "Campaign close-out: 2026-08-03-organizer-type-authority"
---

## Process

| Metric | Value |
| --- | --- |
| user_turns | 42 |
| assistant_turns | 646 |
| tool_calls | 852 |
| avg_tools_per_turn | 20.3 |
| wall_span_hours | 363.76 |

### Tool top 8

| Tool | Count |
| --- | --- |
| read_file | 243 |
| memory | 223 |
| run_in_terminal | 212 |
| grep_search | 93 |
| create_file | 26 |
| file_search | 15 |
| runSubagent | 11 |
| multi_replace_string_in_file | 9 |

## Session

| Field | Value |
| --- | --- |
| session_id | 24a900ba-3e5b-41a8-9e52-252969f49e55 |
| start_event_id | 835f4b6f-37c5-4d1c-bd6d-c8c99641b141 |
| end_event_id_exclusive | 8bb6e240-91f1-4289-9ce1-71aefb719b85 |
| selected_events | 3682 |
| first_timestamp | 2026-07-19T02:50:48.942000Z |
| last_timestamp | 2026-08-03T06:36:22.557000Z |
| slice_digest | sha256:bfe38fc90c6ebcbcbc741e86fdb3d29680f4b6997bfcda14a828cedf8f955f4e |

## Outcome references

- ee002d77b09a6c5ab81bcecb5a79bfa9017b182d
- ee002d77b09a6c5ab81bcecb5a79bfa9017b182d:scraper/organizer_registry.py

## Recompute

1. Read the ledger named by `ledger_path`. Every line is one selected event with the keys `session_id`, `i`, `event_id`, `timestamp`, `type`, `tool_name` and `turn_index`.
2. Recompute `## Process`: `user_turns` counts rows whose `type` is `user.message`; `assistant_turns` counts `assistant.turn_start`; `tool_calls` counts `tool.execution_start`; `avg_tools_per_turn` is `tool_calls / user_turns` rounded to one decimal, or `0` when `user_turns` is zero; `wall_span_hours` is the span between the smallest and the largest `timestamp` expressed in hours and rounded to two decimals; the tool table ranks `tool_name` over `tool.execution_start` rows by count descending, then by name ascending, keeping the first eight.
3. Recompute `selected_events` as the ledger row count, and `first_timestamp` / `last_timestamp` as the smallest / largest `timestamp` value.
4. Recompute `ledger_digest` by hashing the whole ledger file with SHA-256 and prefixing the hex digest with `sha256:`. It must equal `ledger_digest`, and its first twelve hex characters must equal the suffix in the ledger file name.
5. Recompute `slice_digest` from the original transcript alone: take the raw bytes of every selected line with its line terminator removed, join them with a single line feed, hash with SHA-256 and prefix with `sha256:`.
