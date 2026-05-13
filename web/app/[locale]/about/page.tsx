import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { Locale } from "@/lib/types";

export const revalidate = 86400;

const LOCALES: Locale[] = ["zh", "en", "ja"];

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "about" });
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const title = t("heroTitle");
  const description = t("story").slice(0, 160);
  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}/about`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/about`])),
        "x-default": `${base}/zh/about`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}/about`,
      type: "website",
    },
  };
}

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export default async function AboutPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "about" });
  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      <nav className="text-sm text-fg-muted mb-4">
        <Link href={`/${locale}`} className="hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span>{t("heroTitle")}</span>
      </nav>

      <h1 className="text-3xl font-bold mb-6 text-fg-strong">{t("heroTitle")}</h1>

      <section className="mb-8">
        <p className="text-base leading-relaxed text-fg">{t("story")}</p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3 text-fg-strong">{t("sourcesTitle")}</h2>
        <p className="text-base leading-relaxed text-fg">
          {t("sourcesBody")}{" "}
          <Link href={`/${locale}/sources`} className="hover:underline">
            {t("sourcesLinkText")}
          </Link>
          。
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3 text-fg-strong">{t("techTitle")}</h2>
        <p className="text-base leading-relaxed text-fg">
          {t("techBody")}{" "}
          <a
            href="https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
          >
            {t("githubLabel")}
          </a>
          。
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3 text-fg-strong">{t("contactTitle")}</h2>
        <p className="text-base leading-relaxed text-fg">{t("contactBody")}</p>
      </section>
    </main>
  );
}
