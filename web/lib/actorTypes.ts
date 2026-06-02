import enMessages from "@/messages/en.json";
import jaMessages from "@/messages/ja.json";
import zhMessages from "@/messages/zh.json";
import type { Locale } from "@/lib/types";

export const ACTOR_CATEGORIES = [
  "government",
  "semi_official",
  "cultural_institution",
  "academic",
  "commercial_brand",
  "independent_venue",
  "civic_group",
  "media",
  "unknown",
  "traveler",
  "writer",
  "food",
  "art",
] as const;

export type ActorCategory = (typeof ACTOR_CATEGORIES)[number];

const ACTOR_CATEGORY_SET = new Set<string>(ACTOR_CATEGORIES);

const ACTOR_CATEGORY_MESSAGES = {
  zh: zhMessages.actorCategory,
  en: enMessages.actorCategory,
  ja: jaMessages.actorCategory,
} satisfies Record<Locale, Record<ActorCategory, string>>;

export function isActorCategory(value: string | null | undefined): value is ActorCategory {
  return typeof value === "string" && ACTOR_CATEGORY_SET.has(value);
}

export function getActorCategoryLabel(category: ActorCategory, locale: Locale): string {
  return ACTOR_CATEGORY_MESSAGES[locale][category];
}
