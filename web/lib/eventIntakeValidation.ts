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
  business_hours?: string | null;
  organizer?: string | null;
  event_form?: string[] | null;
  primary_language?: string | null;
  category?: string[] | null;
  is_paid?: boolean | null;
  price_info?: string | null;
} & Record<string, unknown>;

export type CollectMissingOptions = {
  requirePrimaryContent?: boolean;
  /** When false, skip the primary-language description check (image step 2). Defaults to true. */
  requirePrimaryDescription?: boolean;
  /** When true, business_hours becomes required (create flow only). Defaults to false. */
  requireBusinessHours?: boolean;
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
  if (opts.requireBusinessHours === true && isBlank(form.business_hours))
    missing.push("business_hours");
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
    const requireDescription = opts.requirePrimaryDescription !== false;
    const lang = typeof opts.primaryLang === "string" ? opts.primaryLang : "";
    if (!VALID_PRIMARY_CONTENT_LANGS.has(lang)) {
      // No fallback to ja — a mixed/empty primary language has no single
      // authoritative content field, so the caller must resolve it explicitly.
      missing.push("primary_name");
      if (requireDescription) missing.push("primary_description");
    } else {
      if (isBlank(form[`name_${lang}`])) missing.push("primary_name");
      if (requireDescription && isBlank(form[`description_${lang}`]))
        missing.push("primary_description");
    }
  }

  return missing;
}

// 錯誤清單顯示順序（使用者指定）
export const MISSING_FIELD_DISPLAY_ORDER: string[] = [
  "primary_language",
  "primary_name",
  "primary_description",
  "paid_choice",
  "category",
  "start_date",
  "end_date",
  "location_name",
  "location_address",
  "business_hours",
  "organizer",
  "event_form",
  "price_info",
];

// missing key → eventIntake i18n label key
export const MISSING_FIELD_LABEL_KEYS: Record<string, string> = {
  primary_language: "primaryLanguageLabel",
  primary_name: "fieldEventName",
  primary_description: "fieldEventDesc",
  paid_choice: "fieldPaidLabel",
  category: "fieldCategory",
  start_date: "fieldStartDate",
  end_date: "fieldEndDate",
  location_name: "fieldVenue",
  location_address: "fieldAddress",
  business_hours: "fieldBusinessHours",
  organizer: "fieldOrganizer",
  event_form: "fieldEventForm",
  price_info: "fieldPriceInfo",
};

export function buildMissingFieldsMessage(
  missing: string[],
  t: (key: string) => string,
): string {
  const present = new Set(missing);
  const ordered = MISSING_FIELD_DISPLAY_ORDER.filter((k) => present.has(k));
  const extras = missing.filter(
    (m) => !MISSING_FIELD_DISPLAY_ORDER.includes(m) && MISSING_FIELD_LABEL_KEYS[m],
  );
  const keys = [...ordered, ...extras];
  if (keys.length === 0) return t("requiredFieldsMissing");
  const lines = keys.map((k) => `✘ ${t(MISSING_FIELD_LABEL_KEYS[k])}`);
  return [t("requiredFieldsMissingTitle"), ...lines].join("\n");
}
