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
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
