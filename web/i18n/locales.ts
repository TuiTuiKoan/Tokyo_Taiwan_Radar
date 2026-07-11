export const LOCALES = ["zh", "en", "ja"] as const;

export type Locale = (typeof LOCALES)[number];