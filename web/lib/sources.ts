export type SourceType =
  | "official"
  | "ticketing"
  | "cinema"
  | "academic"
  | "news"
  | "government"
  | "creator"
  | "other";

export interface SourceInfo {
  id: string;
  name: string;
  type: SourceType;
  frequency: "daily" | "weekly";
  officialUrl: string;
}
