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
  location_address: string | null;
  business_hours: string | null;
  is_paid: boolean | null;
  price_info: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavedEvent {
  id: string;
  user_id: string;
  event_id: string;
  created_at: string;
}

export type Locale = "zh" | "en" | "ja";

export type Category =
  | "movie"
  | "book"
  | "creator"
  | "shop"
  | "brand"
  | "nature"
  | "tech"
  | "tourism"
  | "culture"
  | "literature";

export const CATEGORIES: Category[] = [
  "movie",
  "book",
  "creator",
  "shop",
  "brand",
  "nature",
  "tech",
  "tourism",
  "culture",
  "literature",
];

export const LOCALES: Locale[] = ["zh", "en", "ja"];

/** Return the best available name for an event given the current locale. */
export function getEventName(event: Event, locale: Locale): string {
  return (
    event[`name_${locale}`] ??
    event.name_ja ??
    event.name_zh ??
    event.name_en ??
    "（未命名）"
  );
}

/** Return the best available description for an event given the current locale. */
export function getEventDescription(
  event: Event,
  locale: Locale
): string | null {
  return (
    event[`description_${locale}`] ??
    event.description_ja ??
    event.description_zh ??
    event.description_en ??
    null
  );
}
