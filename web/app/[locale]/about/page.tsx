import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { MascotAvatar } from "@/lib/design";
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
  const image = `${base}/${locale}/about/opengraph-image`;
  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}/about`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/about`])),
        "x-default": `${base}/ja/about`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}/about`,
      type: "website",
      images: [{ url: image, width: 1200, height: 1200, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
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
    <section className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-fg-strong">{t("heroTitle")}</h1>

      <section className="mb-8">
        <p className="text-base leading-relaxed text-fg">
          {t("story")}{" "}
          {t.rich("storyContact", {
            mail: (chunks) => (
              <a
                href="mailto:hello@tokyotaiwanradar.com"
                className="text-green-500 hover:underline"
              >
                {chunks}
              </a>
            ),
          })}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3 text-fg-strong">{t("mascotTitle")}</h2>
        <div className="flex flex-col sm:flex-row gap-5 items-start">
          <MascotAvatar
            variant="framed"
            shape="square"
            size={140}
            className="shrink-0 mx-auto sm:mx-0"
          />
          <p className="text-base leading-relaxed text-fg">{t("mascotBody")}</p>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3 text-fg-strong">{t("sourcesTitle")}</h2>
        <p className="text-base leading-relaxed text-fg">
          {t("sourcesBody")}{" "}
          <Link href={`/${locale}/sources`} className="text-green-500 hover:underline">
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
            className="text-green-500 hover:underline"
          >
            {t("githubLabel")}
          </a>
          。
        </p>
      </section>
    </section>
  );
}
