import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base =
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app";
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin", "/auth", "/api"],
      },
      // Explicitly permit major AI crawlers — prevents future default-block misclassification
      { userAgent: "GPTBot",            allow: "/" },
      { userAgent: "OAI-SearchBot",     allow: "/" },
      { userAgent: "Anthropic-ai",      allow: "/" },
      { userAgent: "Claude-Web",        allow: "/" },
      { userAgent: "PerplexityBot",     allow: "/" },
      { userAgent: "Google-Extended",   allow: "/" },
      { userAgent: "cohere-ai",         allow: "/" },
      { userAgent: "Meta-ExternalAgent", allow: "/" },
      { userAgent: "YouBot",            allow: "/" },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
