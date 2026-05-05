import Link from "next/link";
import { type Event, type Locale, getEventName, getEventLocationName } from "@/lib/types";
import { getTranslations } from "next-intl/server";

interface Props {
  event: Event;
  locale: Locale;
}

/** Extract short city/prefecture name from a Japanese address string.
 *  Searches anywhere in the string (not just at start) to tolerate
 *  〒xxx-xxxx postal-code prefixes and leading whitespace. */
function extractCity(address: string | null): string | null {
  if (!address) return null;
  const m = address.match(/(北海道|東京都|(?:大阪|京都)府|大阪市|京都市|[^\s都道府県\d〒-]{2,4}[都道府県])/);
  if (!m) return null;
  const full = m[1];
  if (full === "北海道") return "北海道";
  if (full === "大阪市" || full === "大阪府") return "大阪";
  if (full === "京都市" || full === "京都府") return "京都";
  if (full === "東京都") return "東京";
  return full.replace(/[都道府県]$/, "");
}

/** Normalize a location_prefectures entry (e.g. "東京都" → "東京"). */
function shortPrefecture(p: string): string {
  if (p === "北海道") return "北海道";
  return p.replace(/[都道府県]$/, "");
}

export default async function EventCard({ event, locale }: Props) {
  const t = await getTranslations("event");
  const tCat = await getTranslations("categories");
  const tOrgType = await getTranslations("organizerType");

  const name = getEventName(event, locale);
  const locationName = getEventLocationName(event, locale);
  const now = new Date();
  const ended = event.end_date && new Date(event.end_date) < now;

  // Derive city label.
  // Priority: location_prefectures (authoritative, set by annotator) → address regex fallback.
  // Single prefecture → show short form (e.g. "東京"); multiple → join with "・".
  const prefectures = (event as any).location_prefectures as string[] | null | undefined;
  const cityLabel: string | null = (() => {
    if (prefectures && prefectures.length >= 1) {
      return prefectures.map(shortPrefecture).join("・");
    }
    return extractCity((event as any).location_address as string | null);
  })();

  return (
    <Link
      href={`/${locale}/events/${event.id}`}
      className="block border border-gray-200 rounded-xl p-4 hover:shadow-md hover:border-green-300 transition bg-white group"
    >
      {/* Status + paid badges */}
      <div className="flex items-center gap-2 mb-2">
        {ended ? (
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
            {t("ended")}
          </span>
        ) : (
          <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
            ●&nbsp;Open
          </span>
        )}
        {event.is_paid === false && (
          <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
            {t("free")}
          </span>
        )}
        {event.is_paid === true && (
          <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full">
            {t("paid")}
          </span>
        )}
        {event.organizer_type?.[0] && event.organizer_type[0] !== "unknown" && (
          <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
            {tOrgType(event.organizer_type[0] as any)}
          </span>
        )}
      </div>

      {/* Title */}
      <h2 className="font-semibold text-gray-900 group-hover:text-green-700 line-clamp-2 leading-snug mb-2">
        {name}
      </h2>

      {/* Categories */}
      {event.category?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {event.category.slice(0, 3).map((cat) => (
            <span
              key={cat}
              className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full"
            >
              {tCat(cat as any)}
            </span>
          ))}
        </div>
      )}

      {/* Date + location */}
      <div className="text-xs text-gray-500 space-y-1">
        {event.start_date && (
          <p>
            📅{" "}
            {new Date(event.start_date).toLocaleDateString(locale, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
            {event.end_date && event.end_date !== event.start_date && (
              <>
                {" "}
                –{" "}
                {new Date(event.end_date).toLocaleDateString(locale, {
                  month: "short",
                  day: "numeric",
                })}
              </>
            )}
          </p>
        )}
        {event.location_name && (
          <p>
            📍{" "}
            {cityLabel && (
              <span className="inline-block bg-gray-100 text-gray-600 text-xs px-1.5 py-0.5 rounded mr-1 font-medium">
                {cityLabel}
              </span>
            )}
            {locationName}
          </p>
        )}
      </div>
    </Link>
  );
}
