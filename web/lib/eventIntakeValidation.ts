// Isomorphic (client + server) required-field validation for the event intake wizard.
// No imports, no side effects — safe to import from both client components and
// server actions so the publish gate and the wizard preflight stay in lock-step.

export const VALID_PRIMARY_CONTENT_LANGS = new Set(["ja", "zh", "en"]);
const VALID_PRIMARY_LANGUAGES = new Set(["ja", "zh", "en", "mixed"]);

export type IntakeFormLike = {
  start_date?: string | null;
  end_date?: string | null;
  location_name?: string | null;
  location_address?: string | null;
  organizer?: string | null;
  event_form?: string[] | null;
  primary_language?: string | null;
  category?: string[] | null;
  is_paid?: boolean | null;
  price_info?: string | null;
} & Record<string, unknown>;

export type CollectMissingOptions = {
  requirePrimaryContent?: boolean;
  primaryLang?: string;
  paidChoiceMade?: boolean;
};

function isBlank(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "")
  );
}

export function collectMissingRequiredFields(
  form: IntakeFormLike,
  opts: CollectMissingOptions = {},
): string[] {
  const missing: string[] = [];

  if (isBlank(form.start_date)) missing.push("start_date");
  if (isBlank(form.end_date)) missing.push("end_date");
  if (isBlank(form.location_name)) missing.push("location_name");
  if (isBlank(form.location_address)) missing.push("location_address");
  if (isBlank(form.organizer)) missing.push("organizer");

  const eventForms = Array.isArray(form.event_form) ? form.event_form : [];
  if (eventForms.length === 0) missing.push("event_form");

  const primaryLanguage =
    typeof form.primary_language === "string" ? form.primary_language : "";
  if (!VALID_PRIMARY_LANGUAGES.has(primaryLanguage)) missing.push("primary_language");

  const categories = Array.isArray(form.category) ? form.category : [];
  if (categories.length === 0) missing.push("category");

  if (opts.paidChoiceMade !== true) missing.push("paid_choice");

  if (form.is_paid === true && isBlank(form.price_info)) missing.push("price_info");

  if (opts.requirePrimaryContent) {
    const lang = typeof opts.primaryLang === "string" ? opts.primaryLang : "";
    if (!VALID_PRIMARY_CONTENT_LANGS.has(lang)) {
      // No fallback to ja — a mixed/empty primary language has no single
      // authoritative content field, so the caller must resolve it explicitly.
      missing.push("primary_content");
    } else {
      const nameValue = form[`name_${lang}`];
      const descValue = form[`description_${lang}`];
      if (isBlank(nameValue) || isBlank(descValue)) missing.push("primary_content");
    }
  }

  return missing;
}
