"use client";

import { useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Locale } from "@/lib/types";
import { shortPrefecture } from "@/lib/cityLabel";
import { matchesLocation } from "@/lib/locationMarkers";
import { matchesCity, REGIONS_WITH_CITY, type RegionWithCity } from "@/lib/regionPrefectures";

// ── Serialisable types (server → client) ──────────────────────────────────────

export interface MovieEventRow {
  id: string;
  name_ja: string | null;
  name_zh: string | null;
  name_en: string | null;
  work_id: string | null;
  location_name: string | null;
  location_address: string | null;
  source_url: string;
  start_date: string | null;
  end_date: string | null;
  location_prefectures: string[] | null;
}

export interface WorkGroupData {
  /** work_id, or "ev_<id>" for standalone events */
  key: string;
  displayTitle: string;
  director: string | null;
  year: number | null;
  posterUrl: string | null;
  events: MovieEventRow[];
  /** sorted short-prefecture list; "_other" for events with no prefecture */
  cities: string[];
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function eventCities(ev: MovieEventRow): string[] {
  const prefs = ev.location_prefectures ?? [];
  if (prefs.length === 0) return ["_other"];
  return prefs.map((p) => shortPrefecture(p.trim())).filter(Boolean);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}

function fmtRange(start: string | null, end: string | null): string {
  if (!start) return "";
  const s = fmtDate(start);
  if (!end || end.slice(0, 10) === start.slice(0, 10)) return s;
  return `${s} – ${fmtDate(end)}`;
}

// ── Main component ────────────────────────────────────────────────────────────

interface Labels {
  director: string;
  viewDetails: string;
  otherCity: string;
}

interface Props {
  groups: WorkGroupData[];
  locale: Locale;
  labels: Labels;
}

export default function MovieWorksList({ groups, locale, labels }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const sp = useSearchParams();

  const filtered = useMemo(() => {
    const q = sp.get("q")?.trim().toLowerCase() ?? "";
    const location = sp.get("location") ?? "";
    const city = sp.get("city") ?? "";

    return groups.filter((group) => {
      // Keyword: match display title or director
      if (q) {
        const hay = [group.displayTitle, group.director]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }

      // Location / city: at least one event in the group must match
      if (location || city) {
        const anyMatch = group.events.some((ev) => {
          if (location && !matchesLocation(ev, location)) return false;
          if (city && (REGIONS_WITH_CITY as readonly string[]).includes(location)) {
            if (!matchesCity(city, ev.location_address, ev.location_prefectures, location as RegionWithCity)) return false;
          }
          return true;
        });
        if (!anyMatch) return false;
      }

      return true;
    });
  }, [groups, sp]);

  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  if (filtered.length === 0) {
    return <p className="text-center text-fg-muted mt-12 text-sm">該当する作品がありません</p>;
  }

  return (
    <div className="space-y-2">
      {filtered.map((group) => (
        <WorkRow
          key={group.key}
          group={group}
          locale={locale}
          labels={labels}
          expanded={expanded}
          onToggle={toggle}
        />
      ))}
    </div>
  );
}

// ── WorkRow ───────────────────────────────────────────────────────────────────

interface WorkRowProps {
  group: WorkGroupData;
  locale: Locale;
  labels: Labels;
  expanded: Set<string>;
  onToggle: (key: string) => void;
}

function WorkRow({ group, locale, labels, expanded, onToggle }: WorkRowProps) {
  // Build city → events map
  const cityMap = useMemo(() => {
    const m = new Map<string, MovieEventRow[]>();
    for (const ev of group.events) {
      for (const city of eventCities(ev)) {
        const bucket = m.get(city) ?? [];
        bucket.push(ev);
        m.set(city, bucket);
      }
    }
    return m;
  }, [group.events]);

  // Use pre-computed cities order (named cities first, "_other" last)
  const cities = group.cities.filter((c) => cityMap.has(c));

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* ── Work header row ── */}
      <div className="flex items-start gap-3 p-3 bg-surface">
        {/* Poster thumbnail */}
        {group.posterUrl ? (
          <Image
            src={group.posterUrl}
            alt={group.displayTitle}
            width={40}
            height={56}
            className="w-10 h-14 object-cover rounded flex-shrink-0"
            unoptimized
          />
        ) : (
          <div className="w-10 h-14 bg-fg-muted/10 rounded flex-shrink-0 flex items-center justify-center text-lg text-fg-muted">
            🎬
          </div>
        )}

        {/* Title + meta + city badges */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm leading-snug line-clamp-2">
            {group.displayTitle}
          </p>
          {(group.director || group.year) && (
            <p className="text-xs text-fg-muted mt-0.5">
              {group.director && `${labels.director}: ${group.director}`}
              {group.director && group.year && " · "}
              {group.year}
            </p>
          )}

          {/* City badges */}
          <div className="flex flex-wrap gap-1 mt-2">
            {cities.map((city) => {
              const expKey = `${group.key}__${city}`;
              const isOpen = expanded.has(expKey);
              const cityLabel = city === "_other" ? labels.otherCity : city;
              return (
                <button
                  key={city}
                  onClick={() => onToggle(expKey)}
                  aria-expanded={isOpen}
                  className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                    isOpen
                      ? "bg-green-600 text-white border-green-600"
                      : "border-border text-fg-muted hover:border-green-600 hover:text-green-700"
                  }`}
                >
                  {cityLabel}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Expanded city panel ── */}
      {cities.map((city) => {
        const expKey = `${group.key}__${city}`;
        if (!expanded.has(expKey)) return null;

        const cityEvents = (cityMap.get(city) ?? []).slice().sort((a, b) =>
          (a.start_date ?? "").localeCompare(b.start_date ?? ""),
        );

        // Group by theater (location_name)
        const byTheater = new Map<string, MovieEventRow[]>();
        for (const ev of cityEvents) {
          const key = ev.location_name ?? "";
          const bucket = byTheater.get(key) ?? [];
          bucket.push(ev);
          byTheater.set(key, bucket);
        }

        return (
          <div
            key={city}
            className="border-t border-border bg-bg px-4 py-3 space-y-3"
          >
            {[...byTheater.entries()].map(([theater, tevs]) => (
              <div key={theater}>
                {theater && (
                  <p className="text-sm font-medium text-fg">{theater}</p>
                )}
                {tevs.map((ev) => (
                  <div
                    key={ev.id}
                    className="flex items-center justify-between text-xs text-fg-muted mt-1"
                  >
                    <span>{fmtRange(ev.start_date, ev.end_date)}</span>
                    <Link
                      href={`/${locale}/events/${ev.id}`}
                      className="text-green-600 hover:underline ml-4"
                    >
                      {labels.viewDetails} →
                    </Link>
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
