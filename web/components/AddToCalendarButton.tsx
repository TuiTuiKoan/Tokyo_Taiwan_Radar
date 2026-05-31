"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { type Locale } from "@/lib/types";

interface Props {
  title: string;
  description?: string | null;
  startDate: string;            // ISO UTC string
  endDate?: string | null;
  businessHours?: string | null;
  location?: string | null;
  eventUrl: string;             // absolute radar URL
  locale: Locale;
}

const _TIME_RE =
  /(\d{1,2}):(\d{2})\s*[〜～\-–ー~]\s*(\d{1,2}):(\d{2})|(\d{1,2}):(\d{2})/;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function fmtUTC(d: Date): string {
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`
  );
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
}

function icsEscape(s: string): string {
  return s
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\n/g, "\\n");
}

function buildCalData(
  title: string,
  description: string | null | undefined,
  startDate: string,
  endDate: string | null | undefined,
  businessHours: string | null | undefined,
  location: string | null | undefined,
  eventUrl: string,
  locale: Locale
) {
  // Normalize full-width digits/colon → half-width before regex matching
  const norm = (businessHours ?? "")
    .replace(/[０-９]/g, (d) => String.fromCharCode(d.charCodeAt(0) - 0xfee0))
    .replace(/：/g, ":");

  const startDay = startDate.slice(0, 10);
  const endDay = endDate?.slice(0, 10) ?? startDay;
  const isSingleDay = !endDate || startDay === endDay;

  let googleStart: string;
  let googleEnd: string;
  let icsStartLine: string;
  let icsEndLine: string;
  let timeStr: string | null = null;

  if (isSingleDay) {
    const match = _TIME_RE.exec(norm);
    if (match) {
      let sh: number, sm: number, eh: number, em: number;
      if (match[1] !== undefined) {
        // HH:MM ~ HH:MM (both start and end)
        sh = parseInt(match[1]);
        sm = parseInt(match[2]);
        eh = parseInt(match[3]);
        em = parseInt(match[4]);
      } else {
        // only start time → end = start + 1h
        sh = parseInt(match[5]);
        sm = parseInt(match[6]);
        eh = sh + 1;
        em = sm;
      }

      const [sy, smo, sda] = startDay.split("-").map(Number);
      // Build UTC instants (JST = UTC+9, so subtract 9h)
      const startUtc = new Date(Date.UTC(sy, smo - 1, sda, sh - 9, sm));
      let endUtc = new Date(Date.UTC(sy, smo - 1, sda, eh - 9, em));
      // Overnight check: if end ≤ start, advance end by 1 day
      if (endUtc <= startUtc) {
        endUtc = new Date(endUtc.getTime() + 24 * 60 * 60 * 1000);
      }

      // Derive JST wall-clock times for Google Calendar (ctz=Asia/Tokyo)
      const startJSTDate = new Date(startUtc.getTime() + 9 * 3600 * 1000);
      const endJSTDate = new Date(endUtc.getTime() + 9 * 3600 * 1000);
      googleStart =
        `${startJSTDate.getUTCFullYear()}${pad(startJSTDate.getUTCMonth() + 1)}${pad(startJSTDate.getUTCDate())}` +
        `T${pad(startJSTDate.getUTCHours())}${pad(startJSTDate.getUTCMinutes())}00`;
      googleEnd =
        `${endJSTDate.getUTCFullYear()}${pad(endJSTDate.getUTCMonth() + 1)}${pad(endJSTDate.getUTCDate())}` +
        `T${pad(endJSTDate.getUTCHours())}${pad(endJSTDate.getUTCMinutes())}00`;

      icsStartLine = `DTSTART:${fmtUTC(startUtc)}`;
      icsEndLine = `DTEND:${fmtUTC(endUtc)}`;
      timeStr = `${pad(sh)}:${pad(sm)}〜${pad(eh)}:${pad(em)}`;
    } else {
      // All-day single day
      const startYMD = fmtDate(startDate);
      const d = new Date(startDate);
      d.setUTCDate(d.getUTCDate() + 1);
      const endExclYMD = `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
      googleStart = startYMD;
      googleEnd = endExclYMD;
      icsStartLine = `DTSTART;VALUE=DATE:${startYMD}`;
      icsEndLine = `DTEND;VALUE=DATE:${endExclYMD}`;
    }
  } else {
    // Multi-day all-day
    const startYMD = fmtDate(startDate);
    const ed = new Date(endDate!);
    ed.setUTCDate(ed.getUTCDate() + 1);
    const endExclYMD = `${ed.getUTCFullYear()}${pad(ed.getUTCMonth() + 1)}${pad(ed.getUTCDate())}`;
    googleStart = startYMD;
    googleEnd = endExclYMD;
    icsStartLine = `DTSTART;VALUE=DATE:${startYMD}`;
    icsEndLine = `DTEND;VALUE=DATE:${endExclYMD}`;
  }

  // Build description parts (must use timeZone: "UTC" for toLocaleDateString
  // because start/end_date stores JST calendar day as UTC midnight)
  const startFmt = new Date(startDate).toLocaleDateString(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
  const endFmt = endDate
    ? new Date(endDate).toLocaleDateString(locale, {
        year: "numeric",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      })
    : null;
  const dateStr =
    endFmt && endFmt !== startFmt ? `${startFmt} 〜 ${endFmt}` : startFmt;
  const locStr = location ? `📍 ${location}` : null;
  const linkStr = `🔗 ${eventUrl}`;

  const descForGoogle =
    (description ?? "").slice(0, 280) +
    ((description?.length ?? 0) > 280 ? "…" : "");

  const googleDescParts = [
    descForGoogle || null,
    `📅 ${dateStr}`,
    timeStr ? `🕐 ${timeStr}` : null,
    locStr,
    linkStr,
  ].filter((x): x is string => x !== null && x !== "");

  const googleParams = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    dates: `${googleStart}/${googleEnd}`,
    details: googleDescParts.join("\n"),
    ...(location ? { location } : {}),
    ...(timeStr ? { ctz: "Asia/Tokyo" } : {}),
  });
  const googleUrl = `https://calendar.google.com/calendar/render?${googleParams.toString()}`;

  // ICS description parts
  const icsDescParts = [
    description ?? null,
    `📅 ${dateStr}`,
    timeStr ? `🕐 ${timeStr}` : null,
    locStr,
    linkStr,
  ].filter((x): x is string => x !== null && x !== "");

  const icsLines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    icsStartLine,
    icsEndLine,
    `SUMMARY:${icsEscape(title)}`,
  ];
  if (icsDescParts.length > 0) {
    icsLines.push(`DESCRIPTION:${icsEscape(icsDescParts.join("\n"))}`);
  }
  if (location) {
    icsLines.push(`LOCATION:${icsEscape(location)}`);
  }
  icsLines.push(`URL:${eventUrl}`);
  icsLines.push("END:VEVENT");
  icsLines.push("END:VCALENDAR");

  const ics = icsLines.join("\r\n");

  return { googleUrl, ics };
}

export default function AddToCalendarButton({
  title,
  description,
  startDate,
  endDate,
  businessHours,
  location,
  eventUrl,
  locale,
}: Props) {
  const t = useTranslations("event");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const calData = useMemo(
    () =>
      buildCalData(
        title,
        description,
        startDate,
        endDate,
        businessHours,
        location,
        eventUrl,
        locale
      ),
    [title, description, startDate, endDate, businessHours, location, eventUrl, locale]
  );

  function handleApple() {
    const blob = new Blob([calData.ics], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "event.ics";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative w-[108px] min-w-[108px] max-w-[108px]">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1.5 w-full border border-line bg-paper dark:bg-elevated text-fg-strong hover:bg-muted py-2 px-2.5 rounded-xl transition"
      >
        <span aria-hidden="true">📅</span>
        <span className="text-sm truncate">{t("addToCalendar")}</span>
        <span className="ml-auto text-fg-subtle text-xs" aria-hidden="true">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-line rounded-xl shadow-lg overflow-hidden z-20">
          <a
            href={calData.googleUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 text-sm text-fg-strong hover:bg-muted transition"
            onClick={() => setOpen(false)}
          >
            <span aria-hidden="true">📅</span>
            <span>{t("addToGoogleCalendar")}</span>
          </a>
          <button
            type="button"
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-fg-strong hover:bg-muted transition text-left border-t border-line"
            onClick={handleApple}
          >
            <span aria-hidden="true">🍎</span>
            <span>{t("addToAppleCalendar")}</span>
          </button>
        </div>
      )}
    </div>
  );
}
