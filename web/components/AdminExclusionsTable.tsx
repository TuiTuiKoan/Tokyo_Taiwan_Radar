"use client";

import { useState, useSyncExternalStore, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  createExclusion,
  toggleExclusion,
  deleteExclusion,
  reEnableExclusion,
  type SourceExclusionRow,
} from "@/app/actions/source-exclusions";
import { type Locale } from "@/lib/types";
import DesignSelect from "@/components/DesignSelect";

interface Props {
  rows: SourceExclusionRow[];
  knownSources: string[];
  locale: Locale;
}

type MatchField = "raw_title" | "raw_description" | "raw_title_or_description";
type Ttl = "permanent" | "30" | "90" | "365";

// Subscribe to a 60s tick so relative-time labels stay roughly fresh.
// useSyncExternalStore is React's canonical pattern for client-only values
// (avoids hydration mismatch and the set-state-in-effect lint rule).
function subscribeToMinute(cb: () => void) {
  const id = setInterval(cb, 60_000);
  return () => clearInterval(id);
}
function getNowMs() {
  return Date.now();
}
function getServerNowMs() {
  return 0;
}

export default function AdminExclusionsTable({ rows, knownSources }: Props) {
  const t = useTranslations("admin");
  const router = useRouter();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState(() => ({
    source_name: searchParams.get("prefill_source") ?? "",
    pattern: searchParams.get("prefill_pattern") ?? "",
    pattern_type: "substring" as "substring" | "regex",
    match_field: "raw_title" as MatchField,
    reason: "",
    ttl: "permanent" as Ttl,
  }));

  // Now timestamp captured client-side; 0 on server (avoids hydration mismatch).
  const nowMs = useSyncExternalStore(subscribeToMinute, getNowMs, getServerNowMs);

  const hasOverbroad = rows.some(
    (r) => r.is_active && r.sample_title && /台|湾|タイワン|台灣/.test(r.sample_title)
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let expires_at: string | null = null;
    if (form.ttl !== "permanent") {
      const days = parseInt(form.ttl, 10);
      expires_at = new Date(Date.now() + days * 86400_000).toISOString();
    }
    const result = await createExclusion({
      source_name: form.source_name,
      pattern: form.pattern,
      pattern_type: form.pattern_type,
      match_field: form.match_field,
      reason: form.reason,
      expires_at,
    });
    if (!result.ok) {
      setError(result.error ?? "failed");
      return;
    }
    setForm({
      source_name: "",
      pattern: "",
      pattern_type: "substring",
      match_field: "raw_title",
      reason: "",
      ttl: "permanent",
    });
    startTransition(() => router.refresh());
  }

  async function onToggle(row: SourceExclusionRow) {
    setBusyId(row.id);
    await toggleExclusion({ id: row.id, is_active: !row.is_active });
    setBusyId(null);
    startTransition(() => router.refresh());
  }

  async function onReEnable(row: SourceExclusionRow) {
    setBusyId(row.id);
    await reEnableExclusion({ id: row.id });
    setBusyId(null);
    startTransition(() => router.refresh());
  }

  async function onDelete(row: SourceExclusionRow) {
    if (!confirm(t("exclusionsConfirmDelete"))) return;
    setBusyId(row.id);
    await deleteExclusion({ id: row.id });
    setBusyId(null);
    startTransition(() => router.refresh());
  }

  function fmtRel(iso: string | null): string {
    if (!iso || nowMs === 0) return "—";
    const ms = nowMs - new Date(iso).getTime();
    const d = Math.floor(ms / 86400_000);
    if (d <= 0) return "<1d";
    if (d < 30) return `${d}d`;
    return `${Math.floor(d / 30)}mo`;
  }

  function hitsClass(n: number): string {
    if (n === 0) return "text-fg-subtle";
    if (n <= 5) return "text-green-600";
    if (n <= 20) return "text-amber-600";
    return "text-red-600 font-semibold";
  }

  return (
    <div className="space-y-6">
      {hasOverbroad && (
        <div className="rounded border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          {t("exclusionsOverbroadWarn")}
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="rounded border border-line bg-surface p-4 space-y-3"
      >
        <h2 className="text-base font-semibold">{t("exclusionsAddTitle")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-fg-muted mb-1">
              {t("exclusionsSourceLabel")}
            </label>
            <input
              list="known-sources"
              required
              className="w-full border rounded px-2 py-1 text-sm"
              value={form.source_name}
              onChange={(e) => setForm({ ...form, source_name: e.target.value })}
            />
            <datalist id="known-sources">
              {knownSources.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </div>
          <div>
            <label className="block text-xs text-fg-muted mb-1">
              {t("exclusionsPatternLabel")}
            </label>
            <input
              required
              minLength={3}
              className="w-full border rounded px-2 py-1 text-sm font-mono"
              value={form.pattern}
              onChange={(e) => setForm({ ...form, pattern: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs text-fg-muted mb-1">
              {t("exclusionsTypeLabel")}
            </label>
            <DesignSelect
              value={form.pattern_type}
              onChange={(v) =>
                setForm({
                  ...form,
                  pattern_type: v as "substring" | "regex",
                })
              }
              options={[
                { value: "substring", label: t("exclusionsTypeSubstring") },
                { value: "regex", label: t("exclusionsTypeRegex") },
              ]}
            />
          </div>
          <div>
            <label className="block text-xs text-fg-muted mb-1">
              {t("exclusionsFieldLabel")}
            </label>
            <DesignSelect
              value={form.match_field}
              onChange={(v) =>
                setForm({ ...form, match_field: v as MatchField })
              }
              options={[
                { value: "raw_title", label: "raw_title" },
                { value: "raw_description", label: "raw_description" },
                { value: "raw_title_or_description", label: "raw_title_or_description" },
              ]}
            />
          </div>
          <div>
            <label className="block text-xs text-fg-muted mb-1">
              {t("exclusionsTtlLabel")}
            </label>
            <DesignSelect
              value={form.ttl}
              onChange={(v) => setForm({ ...form, ttl: v as Ttl })}
              options={[
                { value: "permanent", label: t("exclusionsTtlPermanent") },
                { value: "30", label: t("exclusionsTtlDays", { days: 30 }) },
                { value: "90", label: t("exclusionsTtlDays", { days: 90 }) },
                { value: "365", label: t("exclusionsTtlDays", { days: 365 }) },
              ]}
            />
          </div>
        </div>
        <div>
          <label className="block text-xs text-fg-muted mb-1">
            {t("exclusionsReasonLabel")}
          </label>
          <textarea
            rows={2}
            className="w-full border rounded px-2 py-1 text-sm"
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
          />
        </div>
        {error && <div className="text-sm text-red-600">{error}</div>}
        <button
          type="submit"
          disabled={pending}
          className="px-4 py-1.5 rounded bg-green-600 text-white text-sm hover:bg-green-700 disabled:opacity-50"
        >
          {t("exclusionsSubmit")}
        </button>
      </form>

      {rows.length === 0 ? (
        <div className="text-sm text-fg-muted py-8 text-center">
          {t("exclusionsEmpty")}
        </div>
      ) : (
        <div className="overflow-x-auto rounded border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-elevated text-xs text-fg-muted">
              <tr>
                <th className="px-3 py-2 text-left">source</th>
                <th className="px-3 py-2 text-left">pattern</th>
                <th className="px-3 py-2 text-center">type</th>
                <th className="px-3 py-2 text-center">field</th>
                <th className="px-3 py-2 text-right">{t("exclusionsHits30d")}</th>
                <th className="px-3 py-2 text-left">{t("exclusionsSampleTitle")}</th>
                <th className="px-3 py-2 text-right">{t("exclusionsLifetimeHits")}</th>
                <th className="px-3 py-2 text-center">{t("exclusionsLastMatched")}</th>
                <th className="px-3 py-2 text-center">{t("exclusionsStatusCol")}</th>
                <th className="px-3 py-2 text-center">{t("exclusionsActiveToggle")}</th>
                <th className="px-3 py-2 text-center">—</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const autoDisabled = r.auto_disabled_at !== null;
                let statusBadge: React.ReactNode;
                if (autoDisabled) {
                  const reasonKey =
                    r.auto_disabled_reason === "expired"
                      ? "exclusionsStatusExpired"
                      : "exclusionsStatusStale";
                  statusBadge = (
                    <span className="text-xs text-red-600">🔴 {t(reasonKey)}</span>
                  );
                } else if (
                  r.expires_at &&
                  nowMs > 0 &&
                  new Date(r.expires_at).getTime() - nowMs <= 7 * 86400_000
                ) {
                  statusBadge = (
                    <span className="text-xs text-amber-600">
                      🟡 {t("exclusionsStatusExpiring")}
                    </span>
                  );
                } else {
                  statusBadge = (
                    <span className="text-xs text-green-600">
                      🟢 {t("exclusionsStatusActive")}
                    </span>
                  );
                }
                return (
                <tr
                  key={r.id}
                  className={`border-t ${!r.is_active || autoDisabled ? "opacity-50" : ""}`}
                >
                  <td className="px-3 py-2">{r.source_name}</td>
                  <td className="px-3 py-2 font-mono text-xs">{r.pattern}</td>
                  <td className="px-3 py-2 text-center text-xs">{r.pattern_type}</td>
                  <td className="px-3 py-2 text-center text-xs">
                    {r.match_field === "raw_title"
                      ? "T"
                      : r.match_field === "raw_description"
                      ? "D"
                      : "T+D"}
                  </td>
                  <td className={`px-3 py-2 text-right ${hitsClass(r.hits_30d)}`}>
                    {r.hits_30d}
                  </td>
                  <td
                    className="px-3 py-2 text-xs text-fg-muted max-w-xs truncate"
                    title={r.sample_title ?? ""}
                  >
                    {r.sample_title ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-fg-muted">
                    {r.match_count}
                  </td>
                  <td className="px-3 py-2 text-center text-xs text-fg-muted">
                    {fmtRel(r.last_matched_at)}
                  </td>
                  <td className="px-3 py-2 text-center">{statusBadge}</td>
                  <td className="px-3 py-2 text-center">
                    {autoDisabled ? (
                      <button
                        disabled={busyId === r.id}
                        onClick={() => onReEnable(r)}
                        className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700 hover:bg-blue-200"
                      >
                        {t("exclusionsReEnable")}
                      </button>
                    ) : (
                      <button
                        disabled={busyId === r.id}
                        onClick={() => onToggle(r)}
                        className={`text-xs px-2 py-0.5 rounded ${
                          r.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-muted text-fg-muted"
                        }`}
                      >
                        {r.is_active ? "ON" : "OFF"}
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <button
                      disabled={busyId === r.id}
                      onClick={() => onDelete(r)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      {t("exclusionsDelete")}
                    </button>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
