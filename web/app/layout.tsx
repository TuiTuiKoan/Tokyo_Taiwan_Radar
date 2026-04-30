import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const BASE =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app";

export const metadata: Metadata = {
  title: {
    template: "%s | Tokyo Taiwan Radar",
    default: "Tokyo Taiwan Radar",
  },
};

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${BASE}/#website`,
      name: "Tokyo Taiwan Radar",
      url: BASE,
      description:
        "彙整日本全國台灣相關文化活動的三語平台（繁體中文・日文・英文）",
      inLanguage: ["zh-TW", "ja", "en"],
      potentialAction: {
        "@type": "SearchAction",
        target: {
          "@type": "EntryPoint",
          urlTemplate: `${BASE}/zh?q={search_term_string}`,
        },
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@type": "Organization",
      "@id": `${BASE}/#organization`,
      name: "Tokyo Taiwan Radar",
      url: BASE,
      description:
        "日本全国の台湾関連イベントを集めたプラットフォーム — Aggregating Taiwan-related cultural events across Japan",
      sameAs: ["https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar"],
    },
  ],
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const headersList = await headers();
  const locale = headersList.get("x-locale") ?? "zh";

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
