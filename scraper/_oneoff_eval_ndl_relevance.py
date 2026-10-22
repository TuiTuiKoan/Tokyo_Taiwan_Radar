"""P5 one-off: measure ndl_opensearch relevance filtering and publication gate.

Spec: docs/specs/active/ndl-relevance-publication/proposal.md (section 1, 2.5).
Not a general tool: it exists to produce the recall / N-removal numbers the
gate flag depends on, and it only READS the database.

Sub-commands (work files live outside the repo, default ~/.ai-notes/ttr/p5-eval/):

  snapshot  freeze ndl + hanmoto pure publications, split P_dev / P_seal, write
            the blind sheet for the development set (no model fields on it).
            With --holdout-after it freezes the first new ndl records instead.
  run       run a candidate system prompt through the real _annotate_one() and
            the real relevance gate; sealed splits need --frozen-sha.
  sheets    blind sheets for the post-freeze labelling steps (A zone, K sample,
            extra K sample, holdout).
  metrics   merge labels and model output, compute recall / N-removal / P_h / H.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SEED = "p5-ndl-2026-10"
WORK_DIR = Path.home() / ".ai-notes" / "ttr" / "p5-eval"
SITE_EVENT_URL = "https://tokyotaiwanradar.com/ja/events/"

COST_CAP_USD = 6.0
# gpt-4o-mini list prices, USD per token.
PRICE_IN = 0.15 / 1_000_000
PRICE_OUT = 0.60 / 1_000_000

TAIWAN_TITLE_WORDS = ("台湾", "臺灣", "台灣", "Taiwan")
S2_MIN_COUNTRIES = 3
_COUNTRIES = (
    "日本", "中国", "韓国", "北朝鮮", "台湾", "臺灣", "台灣", "香港", "マカオ", "モンゴル",
    "インド", "タイ", "ベトナム", "フィリピン", "インドネシア", "マレーシア", "シンガポール",
    "ミャンマー", "カンボジア", "ラオス", "ブルネイ", "パキスタン", "バングラデシュ",
    "スリランカ", "ネパール", "アメリカ", "米国", "カナダ", "メキシコ", "ブラジル", "ロシア",
    "ドイツ", "フランス", "イギリス", "英国", "イタリア", "オーストラリア", "ニュージーランド",
    "トルコ", "イラン", "イスラエル", "サウジアラビア",
)
_COUNTRY_ALT = "|".join(sorted(map(re.escape, _COUNTRIES), key=len, reverse=True))
_COUNTRY_RUN_RE = re.compile(rf"(?:(?:{_COUNTRY_ALT})[・、]){{{S2_MIN_COUNTRIES - 1},}}(?:{_COUNTRY_ALT})")

LABELS = ("R", "N", "B")
KEEP_LABELS = ("R", "B")  # D1: B counts as "should be kept"
VERDICT_ORDER = {"fail": 0, "incomplete": 1, "insufficient": 2, "pass": 3, "not_applicable": 4}

RECALL_POINT_MIN = 0.98
RECALL_LB_MIN = 0.96
N_REMOVAL_MIN = 0.60
MAX_LOST_IN_HOLDOUT = 1
CP_ALPHA = 0.05


# ── hashing / ordering helpers ──────────────────────────────────────────────
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ids_sha256(ids) -> str:
    return sha256_text("\n".join(sorted(ids)))


def order_key(salt: str, event_id: str) -> str:
    return sha256_text(f"{salt}{event_id}")


def event_url(event_id: str) -> str:
    return f"{SITE_EVENT_URL}{event_id}"


# ── stratification and the P_dev / P_seal split (proposal 1.1a) ─────────────
def classify_stratum(title: str) -> str:
    """S1: no Taiwan word in the title; S2: Taiwan word plus a country list; else S3."""
    title = title or ""
    if not any(word in title for word in TAIWAN_TITLE_WORDS):
        return "S1"
    if _COUNTRY_RUN_RE.search(title):
        return "S2"
    return "S3"


def dev_count(n: int) -> int:
    """floor(0.6 * n + 0.5) in integer arithmetic, kept off the edges for n >= 2."""
    count = (6 * n + 5) // 10
    if n >= 2:
        count = min(max(count, 1), n - 1)
    return count


def split_dev_seal(strata_by_id: dict[str, str], seed: str = SEED):
    """Return ({id: 'dev'|'seal'}, per-stratum stats)."""
    by_stratum: dict[str, list[str]] = {}
    for event_id, stratum in strata_by_id.items():
        by_stratum.setdefault(stratum, []).append(event_id)
    split: dict[str, str] = {}
    stats: dict[str, dict[str, int]] = {}
    for stratum in sorted(by_stratum):
        ordered = sorted(by_stratum[stratum], key=lambda event_id: order_key(seed, event_id))
        n_dev = dev_count(len(ordered))
        for index, event_id in enumerate(ordered):
            split[event_id] = "dev" if index < n_dev else "seal"
        stats[stratum] = {"n": len(ordered), "dev": n_dev, "seal": len(ordered) - n_dev}
    return split, stats


def select_dev_sheet(records: list[dict], seed: str = SEED, other_sample: int = 40) -> list[dict]:
    """Step 1: P_dev S1 + S2 in full, plus `other_sample` random from the rest of P_dev."""
    dev = [r for r in records if r["split"] == "dev"]
    chosen = [r for r in dev if r["stratum"] in ("S1", "S2")]
    rest = sorted(
        (r for r in dev if r["stratum"] not in ("S1", "S2")),
        key=lambda r: order_key(seed + "dev-sample", r["id"]),
    )
    return chosen + rest[:other_sample]


# ── text helpers for the blind sheets ───────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")


def plain_excerpt(text: str | None, limit: int = 500) -> str:
    cleaned = re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()
    return cleaned[:limit]


BLIND_HEADER = ("event_id", "url", "title", "description_500", "label")


def blind_rows(records: list[dict], stage: str, seed: str = SEED) -> list[list[str]]:
    """Shuffled rows with an empty label column and NOTHING from any model."""
    ordered = sorted(records, key=lambda r: order_key(f"{seed}sheet-{stage}", r["id"]))
    return [
        [r["id"], event_url(r["id"]), r["raw_title"] or "", plain_excerpt(r["raw_description"]), ""]
        for r in ordered
    ]


def write_csv(path: Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


# ── metrics (proposal 1.4 / 1.6) — pure functions ───────────────────────────
def _upper_tail(p: float, x: int, n: int) -> float:
    """P(X >= x) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x, n + 1))


def cp_lower(x: int, n: int, alpha: float = CP_ALPHA) -> float | None:
    """One-sided Clopper-Pearson lower bound: Beta^-1(alpha; x, n - x + 1).

    n == 0 -> None (no estimate). x == 0 -> 0. x == n -> alpha ** (1 / n).
    Otherwise solved exactly from the binomial tail by bisection.
    """
    if n <= 0:
        return None
    if x <= 0:
        return 0.0
    if x >= n:
        return alpha ** (1.0 / n)
    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2
        if _upper_tail(mid, x, n) < alpha:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def recall_verdict(point: float | None, lower: float | None, extra_sampled: bool) -> str:
    if point is None or lower is None:
        return "not_applicable"
    if point < RECALL_POINT_MIN:
        return "fail"
    if lower >= RECALL_LB_MIN:
        return "pass"
    return "fail" if extra_sampled else "insufficient"


def worst_verdict(verdicts) -> str:
    return min(verdicts, key=lambda v: VERDICT_ORDER[v])


def seal_metrics(rows: list[dict], rule: str, label_key: str, extra_sampled: bool = False) -> dict:
    """Recall and N-removal of `rule` on P_seal.

    rows: {"id", "drops": {rule: bool}, label_key: 'R'|'N'|'B'|None}.
    A = dropped by any rule (must be fully labelled); K = dropped by none
    (labelled sample of it is the estimate for the whole of K).
    """
    a_zone = [r for r in rows if any(r["drops"].values())]
    k_zone = [r for r in rows if not any(r["drops"].values())]
    unlabeled = [r["id"] for r in a_zone if r.get(label_key) not in LABELS]
    if unlabeled:
        return {"rule": rule, "status": "incomplete", "unlabeled_a_zone": unlabeled}

    n_k = len(k_zone)
    sample = [r for r in k_zone if r.get(label_key) in LABELS]
    n = len(sample)
    x = sum(1 for r in sample if r[label_key] in KEEP_LABELS)
    if n_k > 0 and n == 0:
        return {"rule": rule, "status": "insufficient_sample", "n_k": n_k, "n": 0}

    p_hat = (x / n) if n else 0.0
    p_lb = cp_lower(x, n) if n else 0.0

    lost = [r["id"] for r in a_zone if r["drops"][rule] and r[label_key] in KEEP_LABELS]
    kept_a = sum(1 for r in a_zone if not r["drops"][rule] and r[label_key] in KEEP_LABELS)
    a_n = sum(1 for r in a_zone if r[label_key] == "N")
    dropped_n = sum(1 for r in a_zone if r["drops"][rule] and r[label_key] == "N")

    def recall(p: float) -> float | None:
        kept = kept_a + n_k * p
        return _ratio(kept, kept + len(lost))

    def n_removal(p: float) -> float | None:
        return _ratio(dropped_n, a_n + n_k * (1 - p))

    recall_point, recall_lb = recall(p_hat), recall(p_lb)
    removal_point, removal_conservative = n_removal(p_hat), n_removal(p_lb)
    removal_verdict = (
        "not_applicable"
        if removal_point is None
        else ("pass" if removal_conservative is not None and removal_point >= N_REMOVAL_MIN else "fail")
    )
    return {
        "rule": rule,
        "status": "ok",
        "n_k": n_k,
        "n": n,
        "x": x,
        "p_hat": p_hat,
        "p_lb": p_lb,
        "lost_keep_ids": lost,
        "recall_point": recall_point,
        "recall_lower": recall_lb,
        "recall_verdict": recall_verdict(recall_point, recall_lb, extra_sampled),
        "n_removal_point": removal_point,
        "n_removal_conservative": removal_conservative,
        "n_removal_verdict": removal_verdict,
    }


def gate_zone_metrics(rows: list[dict], label_key: str) -> dict:
    """P_h and H: every row dropped by G must be labelled; lost R+B must be <= 1."""
    dropped = [r for r in rows if r["drops"].get("G")]
    unlabeled = [r["id"] for r in dropped if r.get(label_key) not in LABELS]
    if unlabeled:
        return {"status": "incomplete", "verdict": "incomplete", "unlabeled_dropped": unlabeled}
    lost = [r["id"] for r in dropped if r[label_key] in KEEP_LABELS]
    return {
        "status": "ok",
        "n": len(rows),
        "dropped": len(dropped),
        "lost_keep_ids": lost,
        "verdict": "pass" if len(lost) <= MAX_LOST_IN_HOLDOUT else "fail",
    }


# ── run: cost cap and the real annotation / gate path ───────────────────────
def usage_cost(usage) -> float:
    if usage is None:
        return 0.0
    return (getattr(usage, "prompt_tokens", 0) or 0) * PRICE_IN + (
        getattr(usage, "completion_tokens", 0) or 0
    ) * PRICE_OUT


def run_records(records, annotate_fn, gate_fn, cost_cap: float = COST_CAP_USD, workers: int = 4):
    """Annotate records concurrently; stop starting new calls once the cap is hit.

    annotate_fn(record) -> (annotation, usage); gate_fn(record, annotation) -> bool.
    Returns (results, total_cost, stopped_early).
    """
    lock = threading.Lock()
    state = {"cost": 0.0, "stop": False}

    def work(record):
        with lock:
            if state["stop"]:
                return None
        annotation, usage = annotate_fn(record)
        with lock:
            state["cost"] += usage_cost(usage)
            if state["cost"] > cost_cap:
                state["stop"] = True
        return {
            "event_id": record["id"],
            "split": record["split"],
            "record_type": "publication",
            "annotation": annotation,
            "gate_deactivates": bool(gate_fn(record, annotation)),
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            },
        }

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, record) for record in records]
        for future in as_completed(futures):
            outcome = future.result()
            if outcome is not None:
                results.append(outcome)
    return results, state["cost"], state["stop"]


@contextmanager
def _gate_forced_eligible():
    """Evaluation only: let the real gate see a first-pass publication."""
    import annotator

    previous = annotator.PUBLICATION_RELEVANCE_GATE_ENABLED
    annotator.PUBLICATION_RELEVANCE_GATE_ENABLED = True
    try:
        yield
    finally:
        annotator.PUBLICATION_RELEVANCE_GATE_ENABLED = previous


def gate_deactivates(record: dict, annotation: dict) -> bool:
    """Call the production gate. Only the eligibility inputs are forced."""
    import annotator
    from publication_rules import PUBLICATION_NULL_FIELDS

    event = {
        "id": record["id"],
        "source_name": record.get("source_name"),
        "event_form": record.get("event_form"),
        "annotated_at": None,
        "annotation_status": "pending",
    }
    sentinels = {name: "" for name in PUBLICATION_NULL_FIELDS}
    with _gate_forced_eligible():
        return annotator._relevance_gate_update(event, annotation, sentinels, False, True) is not None


def make_annotate_fn(client, feedback_prompt: str, sr_feedback_prompt: str):
    import annotator

    def annotate(record: dict):
        event = {"id": record["id"], "event_form": record.get("event_form")}
        return annotator._annotate_one(
            client,
            record["raw_title"],
            record["raw_description"],
            feedback_prompt,
            sr_feedback_prompt,
            record_type=annotator.record_type_for(event),
        )

    return annotate


SEALED_SPLITS = ("seal", "hanmoto", "holdout")


def check_frozen(split: str, prompt_text: str, frozen_sha: str | None) -> None:
    if split not in SEALED_SPLITS:
        return
    actual = sha256_text(prompt_text)
    if not frozen_sha or frozen_sha != actual:
        raise SystemExit(
            f"refusing to run split '{split}': --frozen-sha must equal the prompt file SHA-256 "
            f"({actual}). Freeze the prompt first."
        )


# ── snapshot ────────────────────────────────────────────────────────────────
_COLUMNS = (
    "id,source_name,raw_title,name_ja,raw_description,description_ja,source_url,"
    "created_at,updated_at,is_active,event_form,annotation_status,annotated_at"
)


def _fetch_all(build_query, page: int = 1000) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        batch = build_query().order("id").range(start, start + page - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page:
            return rows
        start += page


def _exact_count(build_query) -> int:
    return build_query().limit(1).execute().count


def _effective(row: dict) -> dict:
    """Title/description exactly as the annotator main flow derives them."""
    return {
        "id": row["id"],
        "source_name": row.get("source_name"),
        "raw_title": row.get("raw_title") or row.get("name_ja") or "",
        "raw_description": row.get("raw_description") or row.get("description_ja") or "",
        "source_url": row.get("source_url"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "is_active": row.get("is_active"),
        "event_form": row.get("event_form"),
    }


def cmd_snapshot(args) -> None:
    import annotator
    from publication_rules import is_pure_publication_record

    sb = annotator._get_supabase()
    out_dir = Path(args.out_dir)
    taken_at = datetime.now(timezone.utc).isoformat()

    def ndl_query():
        return (
            sb.table("events")
            .select(_COLUMNS, count="exact")
            .eq("source_name", "ndl_opensearch")
            .is_("parent_event_id", "null")
        )

    if args.holdout_after:
        rows = (
            ndl_query().gt("created_at", args.holdout_after).order("created_at").limit(args.limit).execute().data
            or []
        )
        records = [{**_effective(r), "stratum": classify_stratum(_effective(r)["raw_title"]), "split": "holdout"} for r in rows]
        meta = {"kind": "holdout", "after": args.holdout_after, "limit": args.limit, "n": len(records)}
        target = out_dir / "holdout.json"
    else:
        ndl_rows = _fetch_all(ndl_query)
        ndl_count = _exact_count(ndl_query)
        if ndl_count != len(ndl_rows):
            raise SystemExit(f"ndl count mismatch: exact={ndl_count} fetched={len(ndl_rows)}")

        def hanmoto_query():
            return (
                sb.table("events")
                .select(_COLUMNS, count="exact")
                .eq("source_name", "hanmoto")
                .is_("parent_event_id", "null")
                .contains("event_form", ["publication"])
            )

        hanmoto_all = _fetch_all(hanmoto_query)
        hanmoto_count = _exact_count(hanmoto_query)
        if hanmoto_count != len(hanmoto_all):
            raise SystemExit(f"hanmoto count mismatch: exact={hanmoto_count} fetched={len(hanmoto_all)}")
        hanmoto_rows = [r for r in hanmoto_all if is_pure_publication_record(r)]

        ndl_records = [_effective(r) for r in ndl_rows]
        strata = {r["id"]: classify_stratum(r["raw_title"]) for r in ndl_records}
        split, stats = split_dev_seal(strata)
        records = [{**r, "stratum": strata[r["id"]], "split": split[r["id"]]} for r in ndl_records]
        records += [
            {**_effective(r), "stratum": classify_stratum(_effective(r)["raw_title"]), "split": "hanmoto"}
            for r in hanmoto_rows
        ]
        meta = {
            "kind": "snapshot",
            "seed": SEED,
            "strata": stats,
            "ndl_count": len(ndl_records),
            "hanmoto_pure_count": len(hanmoto_rows),
            "hanmoto_inactive": sum(1 for r in hanmoto_rows if not r.get("is_active")),
        }
        target = out_dir / "snapshot.json"
        write_csv(
            out_dir / "blind_dev.csv",
            BLIND_HEADER,
            blind_rows(select_dev_sheet(records), "dev"),
        )

    meta = {**meta, "taken_at": taken_at, "ids_sha256": ids_sha256(r["id"] for r in records)}
    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"meta": meta, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"wrote {target}")


# ── run ─────────────────────────────────────────────────────────────────────
def load_snapshot(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            done.add(json.loads(line)["event_id"])
    return done


def cmd_run(args) -> None:
    import annotator
    from category_feedback import build_feedback_prompt, load_corrections
    from selection_reason_feedback import build_sr_feedback_prompt, load_sr_corrections

    prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
    check_frozen(args.split, prompt_text, args.frozen_sha)

    snapshot = load_snapshot(args.snapshot)
    records = [r for r in snapshot["records"] if r["split"] == args.split]
    out_path = Path(args.out)
    done = _done_ids(out_path)
    todo = [r for r in records if r["id"] not in done]
    print(f"split={args.split} records={len(records)} already_done={len(done)} todo={len(todo)}")

    sb = annotator._get_supabase()
    feedback_prompt = build_feedback_prompt(load_corrections(sb))
    sr_feedback_prompt = build_sr_feedback_prompt(load_sr_corrections(sb))
    client = annotator._get_openai()

    original_prompt = annotator.SYSTEM_PROMPT
    annotator.SYSTEM_PROMPT = prompt_text  # in-process only; the repo constant is untouched
    try:
        results, cost, stopped = run_records(
            todo,
            make_annotate_fn(client, feedback_prompt, sr_feedback_prompt),
            gate_deactivates,
            cost_cap=args.cost_cap,
        )
    finally:
        annotator.SYSTEM_PROMPT = original_prompt

    prompt_sha = sha256_text(prompt_text)
    feedback_sha = sha256_text(feedback_prompt + sr_feedback_prompt)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as handle:
        for result in sorted(results, key=lambda r: r["event_id"]):
            handle.write(
                json.dumps({**result, "prompt_sha": prompt_sha, "feedback_sha": feedback_sha}, ensure_ascii=False)
                + "\n"
            )
    print(
        f"completed={len(results)}/{len(todo)} cost=${cost:.3f} cap=${args.cost_cap:.2f}"
        + ("  STOPPED EARLY: cost cap reached, rerun resumes" if stopped else "")
    )
    print(f"wrote {out_path}")


# ── labels / metrics / sheets ───────────────────────────────────────────────
def load_labels(paths) -> dict[str, dict]:
    """Merge label CSVs. Columns: event_id, blind_label (or label), final_label, reason."""
    merged: dict[str, dict] = {}
    for path in paths:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                event_id = (row.get("event_id") or "").strip()
                if not event_id:
                    continue
                blind = (row.get("blind_label") or row.get("label") or "").strip().upper()
                final = (row.get("final_label") or "").strip().upper()
                for value in (blind, final):
                    if value and value not in LABELS:
                        raise SystemExit(f"{path}: invalid label {value!r} for {event_id}")
                entry = merged.setdefault(event_id, {"blind": "", "final": "", "reason": ""})
                if blind and not entry["blind"]:
                    entry["blind"] = blind
                if final:
                    entry["final"] = final
                if (row.get("reason") or "").strip():
                    entry["reason"] = row["reason"].strip()
    return merged


def load_outputs(paths) -> dict[str, dict]:
    outputs: dict[str, dict] = {}
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                outputs[row["event_id"]] = row
    return outputs


def build_rows(records, labels, outputs) -> list[dict]:
    from sources.ndl_opensearch import _is_taiwan

    rows = []
    for record in records:
        label = labels.get(record["id"], {})
        output = outputs.get(record["id"])
        drops = {"R1": not _is_taiwan(record["raw_title"])}
        if output is not None:
            drops["G"] = bool(output["gate_deactivates"])
        rows.append(
            {
                "id": record["id"],
                "title": record["raw_title"],
                "stratum": record["stratum"],
                "split": record["split"],
                "drops": drops,
                "blind": label.get("blind") or None,
                "final": label.get("final") or label.get("blind") or None,
                "reason": label.get("reason", ""),
                "annotation": (output or {}).get("annotation"),
            }
        )
    return rows


def _with_label(rows, key):
    return [{**r, "label": r[key]} for r in rows]


def _verdict_of(metric: dict, field: str) -> str:
    return metric[field] if metric.get("status") == "ok" else "incomplete"


def report_metrics(rows, extra_sampled: bool) -> dict:
    needs_output = [r["id"] for r in rows if r["split"] in ("seal", "hanmoto", "holdout") and "G" not in r["drops"]]
    if needs_output:
        return {"status": "no_model_output", "ids_without_output": len(needs_output)}

    has_holdout = any(r["split"] == "holdout" for r in rows)
    report: dict = {"status": "ok", "label_sets": {}, "conservative": {}}
    for key in ("final", "blind"):
        keyed = _with_label(rows, key)
        zone = lambda name: [r for r in keyed if r["split"] == name]  # noqa: E731
        report["label_sets"][key] = {
            "seal": {rule: seal_metrics(zone("seal"), rule, "label", extra_sampled) for rule in ("R1", "G")},
            "P_h": gate_zone_metrics(zone("hanmoto"), "label"),
            "H": gate_zone_metrics(zone("holdout"), "label") if has_holdout else None,
        }

    sets = report["label_sets"]
    for rule in ("R1", "G"):
        report["conservative"][f"{rule}_recall"] = worst_verdict(
            [_verdict_of(sets[k]["seal"][rule], "recall_verdict") for k in sets]
        )
        report["conservative"][f"{rule}_n_removal"] = worst_verdict(
            [_verdict_of(sets[k]["seal"][rule], "n_removal_verdict") for k in sets]
        )
    report["conservative"]["P_h"] = worst_verdict([sets[k]["P_h"]["verdict"] for k in sets])
    if has_holdout:
        report["conservative"]["H"] = worst_verdict([sets[k]["H"]["verdict"] for k in sets])
    report["note"] = (
        "A/K split is valid only for the candidate rules R1 and G of this run; "
        "'fail' means the fixed stop rule is not met, not a statistical proof."
    )
    return report


COMPACT_HEADER = (
    "event_id", "url", "title", "stratum", "split", "blind_label", "final_label",
    "adjudication_reason", "R1_drop", "G_drop", "seed", "snapshot_ids_sha256",
)


def compact_csv_rows(rows, meta) -> list[list]:
    sha = meta.get("ids_sha256", "")
    return [
        [
            r["id"], event_url(r["id"]), r["title"], r["stratum"], r["split"],
            r["blind"] or "", r["final"] or "", r["reason"],
            r["drops"].get("R1", ""), r["drops"].get("G", ""), SEED, sha,
        ]
        for r in rows
        if r["blind"] or r["final"]
    ]


def cmd_metrics(args) -> None:
    snapshot = load_snapshot(args.snapshot)
    records = list(snapshot["records"])
    if args.holdout:
        records += load_snapshot(args.holdout)["records"]
    labels = load_labels(args.labels)
    outputs = load_outputs(args.outputs)
    rows = build_rows(records, labels, outputs)
    report = report_metrics(rows, args.extra_sampled)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if args.csv_out:
        write_csv(Path(args.csv_out), COMPACT_HEADER, compact_csv_rows(rows, snapshot["meta"]))
        print(f"wrote {args.csv_out}")


def select_sheet_records(stage: str, rows: list[dict], labeled_ids: set[str], seed: str = SEED) -> list[dict]:
    """Post-freeze sheets. Stage a: unlabeled A zone; k: first 60 of K; extra: next 40 of K."""
    seal = [r for r in rows if r["split"] == "seal"]
    if stage == "a":
        pool = [r for r in rows if r["split"] in ("seal", "hanmoto") and any(r["drops"].values())]
        return [r for r in pool if r["id"] not in labeled_ids]
    k_zone = sorted(
        (r for r in seal if not any(r["drops"].values())),
        key=lambda r: order_key(seed + "k-zone", r["id"]),
    )
    if stage == "k":
        return k_zone[:60]
    if stage == "extra":
        return k_zone[60:100]
    raise ValueError(stage)


def cmd_sheets(args) -> None:
    out_dir = Path(args.out_dir)
    if args.stage == "holdout":
        records = load_snapshot(args.holdout)["records"]
    else:
        snapshot = load_snapshot(args.snapshot)
        rows = build_rows(snapshot["records"], {}, load_outputs(args.outputs))
        if any("G" not in r["drops"] for r in rows if r["split"] in ("seal", "hanmoto")):
            raise SystemExit("run the frozen prompt on seal and hanmoto first (missing model output)")
        labeled = set(load_labels(args.labels)) if args.labels else set()
        chosen = select_sheet_records(args.stage, rows, labeled)
        by_id = {r["id"]: r for r in snapshot["records"]}
        records = [by_id[r["id"]] for r in chosen]
    target = out_dir / f"blind_{args.stage}.csv"
    write_csv(target, BLIND_HEADER, blind_rows(records, args.stage))
    print(f"wrote {target} ({len(records)} rows)")


# ── CLI ─────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot")
    snap.add_argument("--out-dir", default=str(WORK_DIR))
    snap.add_argument("--holdout-after", help="ISO timestamp; freeze the first new ndl records after it")
    snap.add_argument("--limit", type=int, default=30)
    snap.set_defaults(func=cmd_snapshot)

    run = sub.add_parser("run")
    run.add_argument("--snapshot", default=str(WORK_DIR / "snapshot.json"))
    run.add_argument("--prompt-file", required=True)
    run.add_argument("--split", required=True, choices=("dev", "seal", "hanmoto", "holdout"))
    run.add_argument("--frozen-sha")
    run.add_argument("--out", required=True)
    run.add_argument("--cost-cap", type=float, default=COST_CAP_USD)
    run.set_defaults(func=cmd_run)

    sheets = sub.add_parser("sheets")
    sheets.add_argument("--stage", required=True, choices=("a", "k", "extra", "holdout"))
    sheets.add_argument("--snapshot", default=str(WORK_DIR / "snapshot.json"))
    sheets.add_argument("--holdout", default=str(WORK_DIR / "holdout.json"))
    sheets.add_argument("--outputs", nargs="*", default=[])
    sheets.add_argument("--labels", nargs="*", default=[])
    sheets.add_argument("--out-dir", default=str(WORK_DIR))
    sheets.set_defaults(func=cmd_sheets)

    metrics = sub.add_parser("metrics")
    metrics.add_argument("--snapshot", default=str(WORK_DIR / "snapshot.json"))
    metrics.add_argument("--holdout")
    metrics.add_argument("--outputs", nargs="+", required=True)
    metrics.add_argument("--labels", nargs="+", required=True)
    metrics.add_argument("--extra-sampled", action="store_true", help="the one-time extra K sample was taken")
    metrics.add_argument("--csv-out")
    metrics.set_defaults(func=cmd_metrics)
    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
