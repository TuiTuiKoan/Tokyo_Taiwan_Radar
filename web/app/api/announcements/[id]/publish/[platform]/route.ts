import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import type { SocialPlatform, Announcement, Locale } from "@/lib/types";

async function requireAdmin() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { supabase, user: null, error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) };
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return { supabase, user: null, error: NextResponse.json({ error: "Forbidden" }, { status: 403 }) };
  return { supabase, user, error: null };
}

function getTextField(announcement: Announcement, locale: Locale): string {
  return (
    announcement[`title_${locale}`] ??
    announcement.title_ja ??
    announcement.title_zh ??
    announcement.title_en ??
    ""
  );
}

function getBodyField(announcement: Announcement, locale: Locale): string {
  return (
    announcement[`body_${locale}`] ??
    announcement.body_ja ??
    announcement.body_zh ??
    announcement.body_en ??
    ""
  );
}

function getImageField(announcement: Announcement, locale: Locale): string | null {
  return (
    announcement[`image_${locale}`] ??
    announcement.cover_image_url ??
    null
  );
}

// --- Platform publishers ---

async function publishInstagram(
  announcement: Announcement,
  locale: Locale,
  siteUrl: string
): Promise<{ post_id: string }> {
  const accessToken = process.env.META_IG_ACCESS_TOKEN;
  const igUserId = process.env.META_IG_USER_ID;
  if (!accessToken || !igUserId) throw new Error("META_IG_ACCESS_TOKEN / META_IG_USER_ID not configured");

  const caption = [getTextField(announcement, locale), getBodyField(announcement, locale)]
    .filter(Boolean)
    .join("\n\n")
    .slice(0, 2200);

  const imageUrl = getImageField(announcement, locale);
  if (!imageUrl) throw new Error("Instagram requires an image URL");

  // Step 1: Create media container
  const createRes = await fetch(
    `https://graph.facebook.com/v21.0/${igUserId}/media`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_url: imageUrl, caption, access_token: accessToken }),
    }
  );
  const createData = await createRes.json();
  if (!createRes.ok || !createData.id) throw new Error(createData.error?.message ?? "Failed to create IG media container");

  // Step 2: Publish
  const publishRes = await fetch(
    `https://graph.facebook.com/v21.0/${igUserId}/media_publish`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ creation_id: createData.id, access_token: accessToken }),
    }
  );
  const publishData = await publishRes.json();
  if (!publishRes.ok || !publishData.id) throw new Error(publishData.error?.message ?? "Failed to publish IG media");

  return { post_id: publishData.id };
}

async function publishThreads(
  announcement: Announcement,
  locale: Locale,
  _siteUrl: string
): Promise<{ post_id: string }> {
  const accessToken = process.env.THREADS_ACCESS_TOKEN;
  const threadsUserId = process.env.THREADS_USER_ID;
  if (!accessToken || !threadsUserId) throw new Error("THREADS_ACCESS_TOKEN / THREADS_USER_ID not configured");

  const text = [getTextField(announcement, locale), getBodyField(announcement, locale)]
    .filter(Boolean)
    .join("\n\n")
    .slice(0, 500);

  const imageUrl = getImageField(announcement, locale);

  const payload: Record<string, string> = {
    media_type: imageUrl ? "IMAGE" : "TEXT",
    text,
    access_token: accessToken,
  };
  if (imageUrl) payload.image_url = imageUrl;

  // Step 1: Create container
  const createRes = await fetch(
    `https://graph.threads.net/v1.0/${threadsUserId}/threads`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  const createData = await createRes.json();
  if (!createRes.ok || !createData.id) throw new Error(createData.error?.message ?? "Failed to create Threads container");

  // Step 2: Publish
  const publishRes = await fetch(
    `https://graph.threads.net/v1.0/${threadsUserId}/threads_publish`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ creation_id: createData.id, access_token: accessToken }),
    }
  );
  const publishData = await publishRes.json();
  if (!publishRes.ok || !publishData.id) throw new Error(publishData.error?.message ?? "Failed to publish Threads post");

  return { post_id: publishData.id };
}

async function publishFacebook(
  announcement: Announcement,
  locale: Locale,
  _siteUrl: string
): Promise<{ post_id: string }> {
  const accessToken = process.env.META_PAGE_ACCESS_TOKEN;
  const pageId = process.env.META_PAGE_ID;
  if (!accessToken || !pageId) throw new Error("META_PAGE_ACCESS_TOKEN / META_PAGE_ID not configured");

  const message = [getTextField(announcement, locale), getBodyField(announcement, locale)]
    .filter(Boolean)
    .join("\n\n");

  const imageUrl = getImageField(announcement, locale);

  if (imageUrl) {
    // Photo post
    const res = await fetch(
      `https://graph.facebook.com/v21.0/${pageId}/photos`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: imageUrl, caption: message, access_token: accessToken }),
      }
    );
    const data = await res.json();
    if (!res.ok || !data.post_id) throw new Error(data.error?.message ?? "Failed to publish FB photo post");
    return { post_id: data.post_id };
  } else {
    // Text-only post
    const res = await fetch(
      `https://graph.facebook.com/v21.0/${pageId}/feed`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, access_token: accessToken }),
      }
    );
    const data = await res.json();
    if (!res.ok || !data.id) throw new Error(data.error?.message ?? "Failed to publish FB feed post");
    return { post_id: data.id };
  }
}

async function publishLinkedIn(
  announcement: Announcement,
  locale: Locale,
  _siteUrl: string
): Promise<{ post_id: string }> {
  const accessToken = process.env.LINKEDIN_ACCESS_TOKEN;
  const authorUrn = process.env.LINKEDIN_AUTHOR_URN; // e.g. urn:li:person:xxx or urn:li:organization:xxx
  if (!accessToken || !authorUrn) throw new Error("LINKEDIN_ACCESS_TOKEN / LINKEDIN_AUTHOR_URN not configured");

  const commentary = [getTextField(announcement, locale), getBodyField(announcement, locale)]
    .filter(Boolean)
    .join("\n\n")
    .slice(0, 3000);

  const imageUrl = getImageField(announcement, locale);

  const post: Record<string, unknown> = {
    author: authorUrn,
    commentary,
    visibility: "PUBLIC",
    distribution: {
      feedDistribution: "MAIN_FEED",
      targetEntities: [],
      thirdPartyDistributionChannels: [],
    },
    lifecycleState: "PUBLISHED",
    isReshareDisabledByAuthor: false,
  };

  if (imageUrl) {
    // Step 1: Initialize image upload
    const initRes = await fetch("https://api.linkedin.com/rest/images?action=initializeUpload", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        "LinkedIn-Version": "202411",
        "X-Restli-Protocol-Version": "2.0.0",
      },
      body: JSON.stringify({
        initializeUploadRequest: {
          owner: authorUrn,
        },
      }),
    });
    const initData = await initRes.json();
    if (!initRes.ok) throw new Error(initData.message ?? "Failed to initialize LinkedIn image upload");

    const uploadUrl: string = initData.value?.uploadUrl;
    const imageUrn: string = initData.value?.image;
    if (!uploadUrl || !imageUrn) throw new Error("Invalid LinkedIn upload response");

    // Step 2: Upload image bytes
    const imgRes = await fetch(imageUrl);
    if (!imgRes.ok) throw new Error(`Cannot fetch image: ${imageUrl}`);
    const imgBuffer = await imgRes.arrayBuffer();
    await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": imgRes.headers.get("content-type") ?? "image/jpeg" },
      body: imgBuffer,
    });

    post.content = {
      media: {
        title: getTextField(announcement, locale) ?? "",
        id: imageUrn,
      },
    };
  }

  const res = await fetch("https://api.linkedin.com/rest/posts", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      "LinkedIn-Version": "202411",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify(post),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.message ?? `LinkedIn post failed: ${res.status}`);
  }

  // LinkedIn returns post URN in X-RestLi-Id header
  const postId = res.headers.get("x-restli-id") ?? res.headers.get("X-RestLi-Id") ?? "unknown";
  return { post_id: postId };
}

async function publishLine(
  announcement: Announcement,
  locale: Locale,
  siteUrl: string
): Promise<{ post_id: string }> {
  const channelAccessToken = process.env.LINE_CHANNEL_ACCESS_TOKEN;
  if (!channelAccessToken) throw new Error("LINE_CHANNEL_ACCESS_TOKEN not configured");

  const title = getTextField(announcement, locale) ?? "";
  const body = getBodyField(announcement, locale) ?? "";
  const imageUrl = getImageField(announcement, locale);
  const slug = announcement.slug;
  const link = `${siteUrl}/${locale}/announcements/${slug}`;

  const messages: unknown[] = [];

  if (imageUrl) {
    messages.push({
      type: "image",
      originalContentUrl: imageUrl,
      previewImageUrl: imageUrl,
    });
  }

  const textContent = [title, body, link].filter(Boolean).join("\n\n").slice(0, 5000);
  messages.push({ type: "text", text: textContent });

  const res = await fetch("https://api.line.me/v2/bot/message/broadcast", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${channelAccessToken}`,
    },
    body: JSON.stringify({ messages }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.message ?? `LINE broadcast failed: ${res.status}`);
  }

  const requestId = res.headers.get("x-line-request-id") ?? "broadcast";
  return { post_id: requestId };
}

// --- Route handler ---

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; platform: string }> }
) {
  const { id, platform } = await params;
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;

  const validPlatforms: SocialPlatform[] = ["instagram", "threads", "facebook", "linkedin", "line"];
  if (!validPlatforms.includes(platform as SocialPlatform)) {
    return NextResponse.json({ error: "Unknown platform" }, { status: 400 });
  }

  const body = await request.json();
  const locale: Locale = ["zh", "en", "ja"].includes(body.locale) ? body.locale : "zh";

  // Fetch announcement
  const { data: announcement, error: fetchErr } = await supabase
    .from("announcements")
    .select("*")
    .eq("id", id)
    .single();

  if (fetchErr || !announcement) return NextResponse.json({ error: "Announcement not found" }, { status: 404 });

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app";

  // Mark as "publishing"
  const currentSocialStatus = announcement.social_status ?? {};
  await supabase.from("announcements").update({
    social_status: {
      ...currentSocialStatus,
      [platform]: { status: "publishing", locale },
    },
  }).eq("id", id);

  try {
    let result: { post_id: string };

    switch (platform as SocialPlatform) {
      case "instagram":
        result = await publishInstagram(announcement, locale, siteUrl);
        break;
      case "threads":
        result = await publishThreads(announcement, locale, siteUrl);
        break;
      case "facebook":
        result = await publishFacebook(announcement, locale, siteUrl);
        break;
      case "linkedin":
        result = await publishLinkedIn(announcement, locale, siteUrl);
        break;
      case "line":
        result = await publishLine(announcement, locale, siteUrl);
        break;
    }

    await supabase.from("announcements").update({
      social_status: {
        ...currentSocialStatus,
        [platform]: {
          status: "published",
          published_at: new Date().toISOString(),
          post_id: result.post_id,
          locale,
          error: null,
        },
      },
    }).eq("id", id);

    return NextResponse.json({ ok: true, post_id: result.post_id });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);

    await supabase.from("announcements").update({
      social_status: {
        ...currentSocialStatus,
        [platform]: { status: "error", locale, error: message },
      },
    }).eq("id", id);

    return NextResponse.json({ error: message }, { status: 502 });
  }
}
