export type SourceType =
  | "government"
  | "academic"
  | "event_platform"
  | "cinema"
  | "tv"
  | "venue"
  | "department_store"
  | "organizer"
  | "ngo"
  | "news_media"
  | "taiwan_shop"
  | "personal"
  | "creator"
  | "other";

export const SOURCE_TYPES: SourceType[] = [
  "government",
  "academic",
  "event_platform",
  "cinema",
  "tv",
  "venue",
  "department_store",
  "organizer",
  "ngo",
  "news_media",
  "taiwan_shop",
  "personal",
  "creator",
  "other",
];

export interface SourceInfo {
  id: string;
  name: string;
  type: SourceType;
  frequency: "daily" | "weekly";
  officialUrl: string;
}
