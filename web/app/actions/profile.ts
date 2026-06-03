"use server";

import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { ACTOR_CATEGORIES, isActorCategory, type ActorCategory } from "@/lib/actorTypes";

const HANDLE_RE = /^[a-z0-9]+$/;
const SOCIAL_FIELDS = [
  "social_x",
  "social_instagram",
  "social_note",
  "social_facebook",
  "social_threads",
  "social_youtube",
] as const;

export type ProfileInput = {
  user_handle: string;
  organizer_name_zh: string;
  organizer_name_ja: string;
  organizer_name_en: string;
  website_url?: string | null;
  social_x?: string | null;
  social_instagram?: string | null;
  social_note?: string | null;
  social_facebook?: string | null;
  social_threads?: string | null;
  social_youtube?: string | null;
  avatar_url?: string | null;
  category?: string | null;
  region?: string | null;
};

export type ProfileErrorCode =
  | "authRequired"
  | "handleRequired"
  | "handleInvalid"
  | "organizerNamesRequired"
  | "websiteRequired"
  | "websiteInvalid"
  | "categoryInvalid"
  | "handleTaken"
  | "serverMisconfigured"
  | "saveFailed";

export type ProfileActionResult =
  | { ok: true }
  | { ok: false; error: ProfileErrorCode };

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function optionalText(value: unknown): string | null {
  const trimmed = text(value);
  return trimmed ? trimmed : null;
}

function isValidHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

export async function saveProfile(input: ProfileInput): Promise<ProfileActionResult> {
  const supabase = await createServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return { ok: false, error: "authRequired" };
  }

  const userHandle = text(input.user_handle);
  const organizerNameZh = text(input.organizer_name_zh);
  const organizerNameJa = text(input.organizer_name_ja);
  const organizerNameEn = text(input.organizer_name_en);
  const websiteUrl = optionalText(input.website_url);
  const category = optionalText(input.category);

  if (!userHandle) {
    return { ok: false, error: "handleRequired" };
  }
  if (!HANDLE_RE.test(userHandle)) {
    return { ok: false, error: "handleInvalid" };
  }
  if (!organizerNameZh || !organizerNameJa || !organizerNameEn) {
    return { ok: false, error: "organizerNamesRequired" };
  }
  if (websiteUrl && !isValidHttpUrl(websiteUrl)) {
    return { ok: false, error: "websiteInvalid" };
  }
  if (category && !isActorCategory(category)) {
    return { ok: false, error: "categoryInvalid" };
  }

  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceKey) {
    return { ok: false, error: "serverMisconfigured" };
  }

  const payload: {
    user_id: string;
    is_self_registered: true;
    user_handle: string;
    organizer_name_zh: string;
    organizer_name_ja: string;
    organizer_name_en: string;
    website_url: string | null;
    avatar_url: string | null;
    category: ActorCategory | null;
    region: string | null;
  } & Record<(typeof SOCIAL_FIELDS)[number], string | null> = {
    user_id: user.id,
    is_self_registered: true,
    user_handle: userHandle,
    organizer_name_zh: organizerNameZh,
    organizer_name_ja: organizerNameJa,
    organizer_name_en: organizerNameEn,
    website_url: websiteUrl,
    social_x: optionalText(input.social_x),
    social_instagram: optionalText(input.social_instagram),
    social_note: optionalText(input.social_note),
    social_facebook: optionalText(input.social_facebook),
    social_threads: optionalText(input.social_threads),
    social_youtube: optionalText(input.social_youtube),
    avatar_url: optionalText(input.avatar_url),
    category: category && ACTOR_CATEGORIES.includes(category as ActorCategory)
      ? (category as ActorCategory)
      : null,
    region: optionalText(input.region),
  };

  const admin = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    serviceKey,
  );

  const { error } = await admin
    .from("creators")
    .upsert(payload, { onConflict: "user_id" })
    .select("user_id")
    .single();

  if (error) {
    if (error.code === "23505" && error.message.includes("user_handle")) {
      return { ok: false, error: "handleTaken" };
    }
    return { ok: false, error: "saveFailed" };
  }

  return { ok: true };
}
