import { CATEGORIES, EVENT_FORMS, type Category } from "@/lib/types";

export const EVENT_FORM_ALIASES: Record<string, string> = {
  concert: "performance",
  lecture_seminar: "lecture",
  film_screening: "screening",
  festival: "other",
  sports: "other",
};

export const VALID_PRIMARY_LANGUAGES = new Set(["ja", "zh", "en", "mixed"]);

// Descriptions are the translation source. Truncating them here silently caps
// how much of the event the model can translate, so keep the budget large
// enough to carry a full poster/press body (menu, schedule, fees, organizers).
export const DESCRIPTION_PROMPT_MAX_CHARS = 4000;

const DESCRIPTION_PROMPT_LABELS = {
  ja: "説明（日文）",
  zh: "説明（中文）",
  en: "説明（英文）",
} as const;

export type DescriptionPromptInput = {
  ja?: unknown;
  zh?: unknown;
  en?: unknown;
};

/**
 * Build the localized description lines handed to the annotator.
 *
 * A locale field that merely repeats another locale's text is NOT a
 * translation. Labelling it (e.g. "説明（中文）: <Japanese text>") tells the
 * model that the Chinese version already exists and suppresses the real
 * translation, so duplicates are dropped instead of mislabelled.
 */
export function buildDescriptionPromptLines(descriptions: DescriptionPromptInput): string[] {
  const seen = new Set<string>();
  const lines: string[] = [];
  for (const locale of ["ja", "zh", "en"] as const) {
    const raw = descriptions[locale];
    if (typeof raw !== "string") continue;
    const text = raw.trim();
    if (!text) continue;
    const fingerprint = text.replace(/\s+/g, "");
    if (seen.has(fingerprint)) continue;
    seen.add(fingerprint);
    lines.push(
      `${DESCRIPTION_PROMPT_LABELS[locale]}: ${text.slice(0, DESCRIPTION_PROMPT_MAX_CHARS)}`,
    );
  }
  return lines;
}

const FILL_SCORE_THRESHOLD = 3;
const OVERWRITE_SCORE_THRESHOLD = 6;
const POSTAL_RE = /〒\s*\d{3}-\d{4}|\d{3}-\d{4}/;
const ADDRESS_RE = /(?:〒\s*\d{3}-\d{4}|\d{3}-\d{4}|(?:都|道|府|県).{0,20}(?:市|区|町|村|郡)|(?:市|区|町|村|郡)|丁目|番地|号)/;

type LocationField = "location_name" | "location_address";

type MergeContext = {
  bestScore: number;
  lockedFields?: Iterable<string>;
  overwriteableFields?: Iterable<string>;
  currentLocationName?: string | null;
  currentLocationAddress?: string | null;
};

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function normalize(value: string): string {
  return value.replace(/\s+/g, "").trim();
}

function isAddressLike(value: string): boolean {
  return ADDRESS_RE.test(value);
}

function hasPostalCode(value: string): boolean {
  return POSTAL_RE.test(value);
}

function overlaps(current: string, next: string): boolean {
  const currentNormalized = normalize(current);
  const nextNormalized = normalize(next);
  return (
    currentNormalized !== "" &&
    nextNormalized !== "" &&
    (nextNormalized.includes(currentNormalized) || currentNormalized.includes(nextNormalized))
  );
}

function shouldUpgradeLocationName(current: string, next: string, context: MergeContext): boolean {
  const currentNormalized = normalize(current);
  const nextNormalized = normalize(next);
  if (!nextNormalized || nextNormalized === currentNormalized) return false;
  if (isAddressLike(next)) return false;

  const currentAddress = normalize(asString(context.currentLocationAddress));
  if (currentAddress && currentNormalized === currentAddress) return true;

  return nextNormalized.includes(currentNormalized) && nextNormalized.length > currentNormalized.length;
}

function shouldUpgradeLocationAddress(current: string, next: string, context: MergeContext): boolean {
  const currentNormalized = normalize(current);
  const nextNormalized = normalize(next);
  if (!nextNormalized || nextNormalized === currentNormalized) return false;
  if (!isAddressLike(next)) return false;

  const currentName = normalize(asString(context.currentLocationName));
  const currentMatchesName = currentName !== "" && currentNormalized === currentName;
  if (!currentMatchesName && !overlaps(current, next)) return false;

  const currentHasPostalCode = hasPostalCode(current);
  const nextHasPostalCode = hasPostalCode(next);
  const currentHasAddressMarkers = isAddressLike(current);
  const nextHasAddressMarkers = isAddressLike(next);

  if (!currentHasPostalCode && nextHasPostalCode && next.length > current.length) return true;
  if (!currentHasAddressMarkers && nextHasAddressMarkers && next.length > current.length) return true;

  return false;
}

export function shouldApplyAnnotatedLocationField(
  field: LocationField,
  currentValue: unknown,
  nextValue: unknown,
  context: MergeContext,
): boolean {
  const next = asString(nextValue);
  if (!next) return false;

  const lockedFields = new Set(context.lockedFields ?? []);
  if (lockedFields.has(field)) return false;

  const current = asString(currentValue);
  if (!current) return context.bestScore >= FILL_SCORE_THRESHOLD;

  const overwriteableFields = new Set(context.overwriteableFields ?? []);
  if (!overwriteableFields.has(field)) return false;
  if (context.bestScore < OVERWRITE_SCORE_THRESHOLD) return false;

  if (field === "location_name") {
    return shouldUpgradeLocationName(current, next, context);
  }

  return shouldUpgradeLocationAddress(current, next, context);
}

export function sanitizeCategoryValues(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;

  const filtered = [...new Set(value.filter((item): item is string => typeof item === "string"))].filter(
    (item): item is Category => CATEGORIES.includes(item as Category),
  );

  return filtered.length > 0 ? filtered : undefined;
}

export function sanitizeEventFormValues(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;

  const filtered = [
    ...new Set(
      value
        .filter((item): item is string => typeof item === "string")
        .map((item) => EVENT_FORM_ALIASES[item] ?? item),
    ),
  ].filter((item): item is (typeof EVENT_FORMS)[number] => EVENT_FORMS.includes(item as (typeof EVENT_FORMS)[number]));

  return filtered.length > 0 ? filtered : undefined;
}

export function sanitizePrimaryLanguageValue(value: unknown): string | undefined {
  return typeof value === "string" && VALID_PRIMARY_LANGUAGES.has(value) ? value : undefined;
}
