export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Event {
  id: string;
  source_name: string;
  source_id: string;
  source_url: string;
  original_language: string;
  name_ja: string | null;
  name_zh: string | null;
  name_en: string | null;
  description_ja: string | null;
  description_zh: string | null;
  description_en: string | null;
  category: string[];
  start_date: string | null;
  end_date: string | null;
  location_name: string | null;
  location_name_zh: string | null;
  location_name_en: string | null;
  location_address: string | null;
  location_address_zh: string | null;
  location_address_en: string | null;
  location_url: string | null;
  business_hours: string | null;
  business_hours_zh: string | null;
  business_hours_en: string | null;
  is_paid: boolean | null;
  price_info: string | null;
  is_active: boolean;
  parent_event_id: string | null;
  raw_title: string | null;
  raw_description: string | null;
  secondary_source_urls: string[] | null;
  record_links: { title: string; url: string; recommended?: boolean }[] | null;
  official_url?: string | null;
  selection_reason: string | null;
  annotation_status: string;
  annotated_at: string | null;
  force_rescrape?: boolean;
  scraped_at: string | null;
  created_at: string;
  updated_at: string;
  organizer?: string | null;
  organizer_url?: string | null;
  organizer_type?: string[] | null;
  co_organizers?: string[] | null;
  sponsors?: string[] | null;
  event_form?: string[] | null;
  primary_language?: string | null;
  has_japanese_support?: boolean | null;
  has_english_support?: boolean | null;
  has_chinese_support?: boolean | null;
  price_amount?: number | null;
  price_currency?: string | null;
  event_status?: "scheduled" | "cancelled" | "postponed" | "rescheduled" | null;
  performer?: string | null;
}

export type SocialPlatform = "instagram" | "threads" | "facebook" | "linkedin" | "line";

export type SocialPublishStatus = "idle" | "publishing" | "published" | "error";

export interface SocialPlatformStatus {
  status: SocialPublishStatus;
  published_at?: string | null;
  post_id?: string | null;
  locale?: string | null;
  error?: string | null;
}

export interface Announcement {
  id: string;
  slug: string;
  type: "manual" | "weekly_broadcast";
  title_ja: string | null;
  title_zh: string | null;
  title_en: string | null;
  body_ja: string | null;
  body_zh: string | null;
  body_en: string | null;
  cover_image_url: string | null;
  image_ja: string | null;
  image_zh: string | null;
  image_en: string | null;
  is_featured: boolean;
  published_at: string | null;
  social_status: Partial<Record<SocialPlatform, SocialPlatformStatus>>;
  author_id: string | null;
  created_at: string;
  updated_at: string;
  linked_events?: string[]; // event IDs from announcement_events join
}

export interface SavedEvent {
  id: string;
  user_id: string;
  event_id: string;
  created_at: string;
}

export interface EventReport {
  id: string;
  event_id: string;
  report_types: string[];
  locale: string | null;
  status: "pending" | "confirmed" | "dismissed";
  admin_notes: string | null;
  confirmed_at: string | null;
  created_at: string;
}

export type Locale = "zh" | "en" | "ja";

export type Category =
  | "movie"
  | "performing_arts"
  | "senses"
  | "tea_alcohol"
  | "drama"
  | "documentary"
  | "retail"
  | "nature"
  | "tech"
  | "tourism"
  | "lifestyle_food"
  | "books_media"
  | "gender"
  | "parenting"
  | "geopolitics"
  | "art"
  | "lecture"
  | "taiwan_japan"
  | "scholarship"
  | "business"
  | "academic"
  | "competition"
  | "indigenous"
  | "folklore"
  | "history"
  | "urban"
  | "workshop"
  | "literature"
  | "tv_program"
  | "exhibition"
  | "taiwan_mandarin"
  | "healthcare"
  | "report";

export const CATEGORIES: Category[] = [
  "movie",
  "performing_arts",
  "senses",
  "tea_alcohol",
  "drama",
  "documentary",
  "retail",
  "nature",
  "tech",
  "tourism",
  "lifestyle_food",
  "books_media",
  "gender",
  "parenting",
  "geopolitics",
  "art",
  "lecture",
  "taiwan_japan",
  "scholarship",
  "business",
  "academic",
  "competition",
  "indigenous",
  "folklore",
  "history",
  "urban",
  "workshop",
  "literature",
  "tv_program",
  "exhibition",
  "taiwan_mandarin",
  "healthcare",
  "report",
];

export interface CategoryGroup {
  labelKey: string;
  categories: Category[];
}

export const CATEGORY_GROUPS: CategoryGroup[] = [
  {
    labelKey: "group_arts",
    categories: ["movie", "performing_arts", "art", "senses", "tea_alcohol", "drama", "documentary", "indigenous", "folklore", "nature", "literature"],
  },
  {
    labelKey: "group_lifestyle",
    categories: ["lifestyle_food", "retail", "tourism", "competition", "workshop", "exhibition", "books_media", "tv_program"],
  },
  {
    labelKey: "group_knowledge",
    categories: ["business", "academic", "lecture", "taiwan_japan", "scholarship"],
  },
  {
    labelKey: "group_society",
    categories: ["tech", "gender", "parenting", "geopolitics", "history", "taiwan_mandarin", "urban", "healthcare"],
  },
  {
    labelKey: "group_archive",
    categories: ["report"],
  },
];

export const LOCALES: Locale[] = ["zh", "en", "ja"];

/** Return the best available name for an event given the current locale. */
export function getEventName(event: Event, locale: Locale): string {
  return (
    event[`name_${locale}`] ||
    event.name_ja ||
    event.name_zh ||
    event.name_en ||
    "（未命名）"
  );
}

/** Return the best available description for an event given the current locale. */
export function getEventDescription(
  event: Event,
  locale: Locale
): string | null {
  return (
    event[`description_${locale}`] ||
    event.description_ja ||
    event.description_zh ||
    event.description_en ||
    null
  );
}

/** Return the localized venue name (falls back to Japanese original). */
export function getEventLocationName(event: Event, locale: Locale): string | null {
  if (locale === "zh") return event.location_name_zh || event.location_name;
  if (locale === "en") return event.location_name_en || event.location_name;
  return event.location_name;
}

/** Return the localized address (falls back to Japanese original). */
export function getEventLocationAddress(event: Event, locale: Locale): string | null {
  if (locale === "zh") return event.location_address_zh || event.location_address;
  if (locale === "en") return event.location_address_en || event.location_address;
  return event.location_address;
}

/** Return the localized business hours (falls back to Japanese original). */
export function getEventBusinessHours(event: Event, locale: Locale): string | null {
  if (locale === "zh") return event.business_hours_zh || event.business_hours;
  if (locale === "en") return event.business_hours_en || event.business_hours;
  return event.business_hours;
}

export interface SourceExclusion {
  id: string;
  source_name: string;
  pattern: string;
  pattern_type: "substring" | "regex";
  match_field: "raw_title" | "raw_description" | "raw_title_or_description";
  reason: string | null;
  is_active: boolean;
  created_at: string;
  last_matched_at: string | null;
  match_count: number;
  expires_at: string | null;
  auto_disabled_at: string | null;
  auto_disabled_reason: string | null;
}
