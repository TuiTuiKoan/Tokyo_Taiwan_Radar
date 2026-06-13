/**
 * Design System Preview — Storybook-lite for the TTR design library.
 *
 * Visit /zh/design (or /en, /ja) to browse all tokens & components in one page.
 * Useful for visual QA, dark-mode parity check, and onboarding new contributors.
 *
 * Fetches a few real upcoming events from Supabase so the EventCard demo is
 * actually clickable (links navigate to /events/[id]).
 */
import {
  Badge,
  DateChip,
  MascotAvatar,
  DesignDefs,
  color,
  font,
  fontSize,
  fontWeight,
  lineHeight,
  spacing,
  radius,
  shadow,
  motion,
  satoriTokens,
  EventCardMockup,
} from "@/lib/design";
import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";
import { FloatingShapes } from "@/lib/design/FloatingShapes";
import { CATEGORIES, CATEGORY_GROUPS, type Locale, type Event } from "@/lib/types";
import type { BadgeTone } from "@/lib/design";
import { FilterChipDemo } from "./FilterChipDemo";
import EventCard from "@/components/EventCard";
import FilterBar from "@/components/FilterBar";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

export const revalidate = 3600;

async function fetchDemoEvents(): Promise<Event[]> {
  try {
    const supabase = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    );
    const today = new Date().toISOString().slice(0, 10);
    const { data } = await supabase
      .from("events")
      .select("*")
      .eq("is_active", true)
      .eq("annotation_status", "annotated")
      .is("parent_event_id", null)
      .or(`end_date.gte.${today},end_date.is.null`)
      .order("start_date", { ascending: true })
      .limit(10);
    return (data as Event[] | null) ?? [];
  } catch {
    return [];
  }
}

const motifVariants = [0, 1, 2, 3, 4] as const;
const primitiveColorEntries = Object.entries(color.primitive);
const brandColorEntries = Object.entries(color.brand);
const gradientColorEntries = Object.entries(color.gradient);
const fontEntries = Object.entries(font);
const satoriFontEntries = Object.entries(satoriTokens.font);
const fontSizeEntries = Object.entries(fontSize);
const fontWeightEntries = Object.entries(fontWeight);
const lineHeightEntries = Object.entries(lineHeight);
const spacingEntries = Object.entries(spacing);
const radiusEntries = Object.entries(radius);
const shadowEntries = Object.entries(shadow);
const durationEntries = Object.entries(motion.duration);
const easingEntries = Object.entries(motion.easing);

export default async function DesignPage({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}) {
  const { locale } = await params;

  const tones: BadgeTone[] = ["neutral", "success", "info", "warning", "danger", "accent", "brand"];
  const today = new Date();
  const future = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
  const startStr = today.toISOString().slice(0, 10);
  const endStr = future.toISOString().slice(0, 10);

  const demoEvents = await fetchDemoEvents();

  // Pre-resolve translations so EventCardMockup (a non-async component) can use them.
  const tEvent = await getTranslations({ locale, namespace: "event" });
  const tCat = await getTranslations({ locale, namespace: "categories" });
  const tDesign = await getTranslations({ locale, namespace: "designPreview" });
  const tFilters = await getTranslations({ locale, namespace: "filters" });
  const categoriesMap: Record<string, string> = {};
  for (const c of CATEGORIES) {
    try { categoriesMap[c] = tCat(c); } catch { categoriesMap[c] = c; }
  }
  const mockupLabels = {
    open: "Open",
    ended: tEvent("ended"),
    free: tEvent("free"),
    paid: tEvent("paid"),
    save: tEvent("save"),
    detail: locale === "ja" ? "詳細" : locale === "en" ? "Details" : "詳情",
    eventLink: (name: string) => tEvent("eventLink", { name }),
    categories: categoriesMap,
  };

  // Locale-aware copy used by the mockup recreation
  const t = {
    nav: {
      events: locale === "ja" ? "活動一覧" : locale === "en" ? "Events" : "活動列表",
      latest: locale === "ja" ? "最新活動" : locale === "en" ? "Latest" : "最新活動",
      report: locale === "ja" ? "今週速報" : locale === "en" ? "Weekly" : "今週速報",
      stats: locale === "ja" ? "統計" : locale === "en" ? "Stats" : "統計",
      login: locale === "ja" ? "ログイン" : locale === "en" ? "Sign in" : "登入",
    },
    tags: ["M4", locale === "ja" ? "蓮霧主題" : "Lambu Theme", locale === "ja" ? "仿原型風格" : "Prototype-styled", "Top 連結記述"],
    statHero: locale === "ja"
      ? "毎日 09:00 JST 更新 · 47 都道府県 · 100+ 件配信中"
      : locale === "en"
      ? "Daily 09:00 JST · 47 prefectures · 100+ live"
      : "每日 09:00 JST 更新 · 47 都道府県 · 100+ 件配信中",
    heroPara: locale === "ja"
      ? "Tokyo Taiwan Radar は、日本全土で開催される台湾関連のイベントを毎日スクレイピングし、繁中・簡中・英語・日本語の四言語で一覧できるプラットフォームです。映画・展示・講演・市集・グルメまで、あなたに身近で見つける応援を。"
      : locale === "en"
      ? "Tokyo Taiwan Radar gathers Taiwan-related events from across Japan every day and serves them in four languages — film, exhibition, lecture, market, food and more."
      : "Tokyo Taiwan Radar 收錄遍布全日本的台灣相關活動，每日抓取，繁中・簡中・英・日 四語呈現 — 電影、展覽、講座、市集、美食盡收眼底。",
    lineCta: locale === "ja" ? "LINE で受け取る" : locale === "en" ? "Subscribe on LINE" : "用 LINE 接收",
    tabs: [
      locale === "ja" ? "活動" : locale === "en" ? "Events" : "活動",
      locale === "ja" ? "最新活動" : locale === "en" ? "Latest" : "最新活動",
    ],
    tabHint: "Top 出新活動已自動標記 ・ 中介紹順序",
    highlights: [
      {
        kicker: locale === "ja" ? "週刊" : "WEEKLY",
        title: locale === "ja" ? "週刊LIANWU 第12期 即日上線" : locale === "en" ? "Weekly LAMBU #12 is live" : "週刊LAMBU 第12期 即日上線",
        sub: "2026/05/13 · 中部地方の台湾フェア × 5本 / LINE 配信中",
        tint: "from-mascot-pink/25 to-mascot-pink/5",
        pattern: "url(#wavyLinesPink)",
      },
      {
        kicker: locale === "ja" ? "新機能" : "NEW",
        title: locale === "ja" ? "LIANWU 新登場 Extension" : locale === "en" ? "New: LAMBU Browser Extension" : "LAMBU 新登場 Extension",
        sub: "Chrome から1クリックで活動をストック / 日文版先行公開",
        tint: "from-mascot-leaf/40 to-mascot-leaf/5",
        pattern: "url(#wavyLinesGreen)",
      },
      {
        kicker: "EVENT",
        title: locale === "ja" ? "蓮霧祭り 5/20 開催" : locale === "en" ? "Lambu Festival 5/20" : "蓮霧祭 5/20 開催",
        sub: "渋谷ロフトワーク · 入場無料 · 11 組出展中",
        tint: "from-[#FFE9A8]/60 to-[#FFE9A8]/10",
        pattern: "url(#diagStripes)",
      },
    ],
    filterChips: [
      { icon: "🎬", label: locale === "ja" ? "映画" : locale === "en" ? "Film" : "電影" },
      { icon: "🎭", label: locale === "ja" ? "舞台・音楽" : locale === "en" ? "Performing" : "表演" },
      { icon: "🎨", label: locale === "ja" ? "感覚・展示" : locale === "en" ? "Exhibits" : "感覺・展示" },
      { icon: "🛍", label: locale === "ja" ? "雑貨・市集" : locale === "en" ? "Retail" : "雜貨・市集" },
      { icon: "🍜", label: locale === "ja" ? "食・暮らし" : locale === "en" ? "Food" : "食・生活" },
      { icon: "📚", label: locale === "ja" ? "本・媒体" : locale === "en" ? "Books" : "書・媒體" },
    ],
    listTitle: locale === "ja"
      ? `活動列表 · ${demoEvents.length} 件`
      : locale === "en"
      ? `Event list · ${demoEvents.length} items`
      : `活動列表 · ${demoEvents.length} 件`,
    listSort: locale === "ja" ? "日付順" : locale === "en" ? "Sort: date" : "日期順",
    footerNote: locale === "ja"
      ? "M4 · 蓮霧主題（薄ピンクと若葉色）・「Top 出新活動」と分かりやすく · その他活動も日本各地に。蓮霧推荐推。"
      : "M4 · 蓮霧主題（淡粉紅與嫩葉綠）· 自動標記「Top 出新活動」· 其他活動也涵蓋日本各地，蓮霧推荐中。",
  };

  return (
    <div className="relative isolate">
      {/* Defs must come before any element that references the patterns by url(#id) */}
      <DesignDefs />

      {/* Paper-gradient page background — matches mockup */}
      <div
        aria-hidden
        className="fixed inset-0 -z-10 pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg, #FFFDF5 0%, #FFF1EE 58%, #F7FFE8 100%)",
        }}
      />
      {/* Decorative full-page background patterns — Bauhaus geometric shapes */}
      <svg aria-hidden className="fixed inset-0 -z-10 w-full h-full pointer-events-none" preserveAspectRatio="xMidYMin slice" viewBox="0 0 1440 1200">
        {/* Full-page Grid Pattern Base */}
        <rect width="100%" height="100%" fill="url(#gridPink)" opacity="0.85" />
      </svg>

      {/* Floating Bauhaus shapes — ~100 procedurally generated, deterministic. */}
      <FloatingShapes />

      {/* Mock TopNav removed — production <Navbar> is already rendered by [locale]/layout.tsx */}

      <div className="max-w-6xl mx-auto px-4 py-10 space-y-12 relative z-0">

        {/* Hero — mockup-style: mascot left, headline + right-side info card */}
        <section className="relative grid gap-6 md:grid-cols-[260px_1fr] items-center pt-2 text-center md:text-left">
          <div className="relative inline-flex flex-col items-center mx-auto md:mx-0 shrink-0">
            <MascotAvatar variant="inline" size={240} />
            <div
              className="absolute bottom-0 right-4 px-3 py-1.5 bg-paper border-2 text-[10px] font-accent font-black tracking-widest text-[#3A261F] -rotate-6 text-center z-10"
              style={{ borderColor: "var(--color-mocha, #3A261F)" }}
            >
              Lianbu
            </div>
          </div>

          <div className="w-full flex flex-col items-center md:items-start text-center md:text-left mx-auto md:mx-0">
            <h1 className="font-display font-black text-[#3A261F] leading-tight text-3xl tracking-tight">
              <span className="block">{locale === "ja" ? "日本にひそむ" : locale === "en" ? "Hidden across Japan," : "藏在日本的"}</span>
              <span className="block">{locale === "ja" ? "台湾を、" : locale === "en" ? "a Taiwan" : "台灣，"}</span>
              <span className="block">{locale === "ja" ? "蓮霧のように" : locale === "en" ? "that ripens like" : "像蓮霧一樣"}</span>
              <span className="block text-mascot-red">
                {locale === "ja" ? "熟していく。" : locale === "en" ? "a wax apple." : "逐漸成熟。"}
              </span>
            </h1>

            {/* Pill with stats */}
            <div className="mt-3 mb-1 inline-flex items-center px-3 py-1 rounded bg-[#C4E86F]/40 text-[#1F5E2B] text-[10px] sm:text-xs font-bold whitespace-nowrap">
              {t.statHero}
            </div>

            <p className="text-fg-muted text-[10px] mt-2 max-w-xl leading-relaxed mx-auto md:mx-0 text-center md:text-left w-full">
              {t.heroPara}
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3 justify-center md:justify-start w-full">
              <button
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-white text-sm font-bold shadow-sm hover:opacity-90"
                style={{ background: "#06C755" }}
              >
                <span className="w-4 h-4 rounded-sm bg-white text-[10px] leading-4 text-center font-black" style={{ color: "#06C755" }}>L</span>
                {t.lineCta}
              </button>
              <p className="text-[11px] text-fg-muted">
                {tDesign("title")} — <code className="font-mono">{locale}</code>
                {" "}· {tDesign("localeSwitcherLabel")}
                {" "}· <Link href="/zh/design" className="underline">zh</Link>
                {" · "}<Link href="/en/design" className="underline">en</Link>
                {" · "}<Link href="/ja/design" className="underline">ja</Link>
              </p>
              <p className="w-full text-[11px] text-fg-muted leading-relaxed text-center md:text-left">
                {tDesign("subtitle")}
              </p>
            </div>
          </div>

        </section>

        {/* Featured highlights header + horizontal scroll cards */}
        <section className="space-y-3">
          <div className="flex items-end justify-between">
            <h2 className="font-display font-bold text-[#3A261F] text-xl">
              📌 {locale === "ja" ? "注目のお知らせ" : locale === "en" ? "Featured" : "注目のお知らせ"}
            </h2>
            <Link href={`/${locale}/announcements`} className="text-xs text-mascot-pink-deep hover:underline">
              {locale === "ja" ? "過去のお知らせを見る →" : locale === "en" ? "View all →" : "查看更多公告 →"}
            </Link>
          </div>
          <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 -mx-4 px-4 scrollbar-thin">
            {t.highlights.map((h, i) => (
              <div
                key={i}
                className="relative shrink-0 w-72 sm:w-80 snap-start overflow-hidden rounded-lg border border-line/70 p-4 shadow-sm"
                style={{ background: "linear-gradient(135deg, #FFF6D1 0%, #FFE9A8 100%)" }}
              >
                <svg aria-hidden className="absolute top-0 right-0 w-24 h-10 opacity-50 pointer-events-none">
                  <rect width="100%" height="100%" fill={h.pattern} />
                </svg>
                <div
                  className="inline-block px-2 py-0.5 mb-2 text-[10px] font-mono uppercase tracking-widest rounded-sm bg-paper"
                  style={{ color: "#3A261F" }}
                >
                  {h.kicker}
                </div>
                <div className="font-display font-bold text-[#3A261F] text-[15px] sm:text-base leading-snug mb-1">
                  {h.title}
                </div>
                <div className="text-[11px] text-fg-muted leading-snug">
                  {h.sub}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Filter row — real production FilterBar component, wrapped to align rounded corners */}
        <section className="relative z-10 w-full">
          <FilterBar locale={locale} currentFilters={{ timeMode: "active" }} />
        </section>

        {/* List header */}
        <div className="flex items-end justify-between">
          <h2 className="font-display font-bold text-[#3A261F] text-xl">
            {t.listTitle}
            <span className="ml-2 text-xs font-normal text-fg-muted">
              {locale === "ja" ? "（日付順）" : locale === "en" ? "(by date)" : "（日期順）"}
            </span>
          </h2>
          <button className="text-xs text-fg-muted hover:text-fg inline-flex items-center gap-1">
            {t.listSort} <span>▾</span>
          </button>
        </div>

        {/* Mockup-style event row list — matches M4 desktop mockup */}
        <section className="space-y-2 -mt-6">
          {demoEvents.map((event, i) => (
            <EventCardMockup
              key={`mock-${event.id}`}
              event={event}
              locale={locale}
              index={i}
              labels={mockupLabels}
            />
          ))}
        </section>

        {/* Page mockup footer note */}
        <div className="border-t border-line/70 pt-4 text-[11px] text-fg-muted leading-relaxed text-center">
          {t.footerNote}
        </div>

      <Section title={tDesign("tokens.indexTitle")}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <TokenIndexItem label={tDesign("tokens.colorTitle")} count={primitiveColorEntries.length + brandColorEntries.length + gradientColorEntries.length} />
          <TokenIndexItem label={tDesign("tokens.typographyTitle")} count={fontEntries.length + fontSizeEntries.length + fontWeightEntries.length + lineHeightEntries.length} />
          <TokenIndexItem label={tDesign("tokens.spacingTitle")} count={spacingEntries.length} />
          <TokenIndexItem label={tDesign("tokens.radiusTitle")} count={radiusEntries.length} />
          <TokenIndexItem label={tDesign("tokens.shadowTitle")} count={shadowEntries.length} />
          <TokenIndexItem label={tDesign("tokens.motionTitle")} count={durationEntries.length + easingEntries.length} />
        </div>
      </Section>

      {/* Live EventCard grid — real upcoming events, clickable */}
      <Section title={tDesign("liveEventTitle", { count: demoEvents.length })}>
        {demoEvents.length === 0 ? (
          <p className="text-fg-muted text-sm">
            {tDesign("emptyLiveEvents")}
          </p>
        ) : (
          <>
            <p className="text-xs text-fg-muted mb-3">
              {tDesign("liveEventHint")}
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              {demoEvents.map((event) => (
                <EventCard key={event.id} event={event} locale={locale} />
              ))}
            </div>
          </>
        )}
      </Section>

      {/* Mobile preview — same cards but constrained to phone width */}
      <Section title={tDesign("mobilePreviewTitle")}>
        <p className="text-xs text-fg-muted mb-3">
          {tDesign("mobilePreviewNote")}
        </p>
        <div className="mx-auto w-full max-w-[390px] rounded-[2.2rem] border-4 border-fg/70 bg-bg p-3 shadow-xl dark:border-fg/30">
          <div className="rounded-2xl overflow-hidden bg-surface p-3 space-y-3 max-h-[640px] overflow-y-auto">
            {demoEvents.slice(0, 3).map((event) => (
              <EventCard key={`m-${event.id}`} event={event} locale={locale} />
            ))}
          </div>
        </div>
      </Section>

      {/* Mock FilterBar selected chips strip */}
      <Section title={tDesign("components.filterChipStripTitle")}>
        <div className="bg-surface border border-line rounded-lg p-4">
          <div className="text-xs text-fg-muted mb-2">{tDesign("components.filterChipNote")}</div>
          <div className="flex flex-wrap items-center gap-2 px-1">
            <span className="text-xs font-medium text-fg-muted shrink-0">{tFilters("selectedLabel")}</span>
            <FilterChipDemo />
          </div>
        </div>
      </Section>

      <Section title={tDesign("motifs.title")} description={tDesign("motifs.description")}>
        <div className="space-y-6">
          {CATEGORY_GROUPS.map((group) => (
            <div key={group.labelKey} className="space-y-3">
              <div className="flex items-center justify-between gap-3 border-b border-line/70 pb-2">
                <h3 className="text-sm font-display font-bold text-fg">
                  {tDesign("motifs.groupLabel", { group: tCat(group.labelKey) })}
                </h3>
                <span className="font-mono text-xs text-fg-muted">{group.categories.length}</span>
              </div>
              <div className="grid gap-3">
                {group.categories.map((category) => (
                  <div
                    key={category}
                    className="grid gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-[11rem_1fr]"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-fg">{tCat(category)}</div>
                      <code className="mt-1 block truncate font-mono text-[11px] text-fg-muted">{category}</code>
                    </div>
                    <div className="grid grid-cols-5 gap-2 sm:gap-3">
                      {motifVariants.map((variant) => (
                        <div key={`${category}-${variant}`} className="min-w-0 space-y-1" data-design-motif="true">
                          <CategoryThumbnail
                            id={`design-${category}-${variant}`}
                            categories={[category]}
                            className="aspect-square w-full rounded-lg border border-line"
                            forceMotifIdx={variant}
                          />
                          <div className="truncate text-center font-mono text-[10px] text-fg-muted">
                            {tDesign("motifs.variantLabel", { index: variant + 1 })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Color tokens */}
      <Section title={tDesign("tokens.colorTitle")}>
        <div className="space-y-6">
          <TokenSubsection title={tDesign("tokens.primitiveTitle")}>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
              {primitiveColorEntries.map(([name, value]) => (
                <Swatch key={name} name={name} value={value} />
              ))}
            </div>
          </TokenSubsection>
          <TokenSubsection title={tDesign("tokens.brandTitle")}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {brandColorEntries.map(([name, value]) => (
                <Swatch key={name} name={name} value={value} />
              ))}
            </div>
          </TokenSubsection>
          <TokenSubsection title={tDesign("tokens.gradientTitle")}>
            <div className="grid gap-3 sm:grid-cols-2">
              {gradientColorEntries.map(([name, stops]) => (
                <GradientSwatch key={name} name={name} stops={[...stops]} />
              ))}
            </div>
          </TokenSubsection>
        </div>
      </Section>

      {/* Typography */}
      <Section title={tDesign("tokens.typographyTitle")}>
        <div className="space-y-6">
          <TokenSubsection title={tDesign("tokens.fontTitle")}>
            <div className="grid gap-3 sm:grid-cols-2">
              {fontEntries.map(([name, value]) => (
                <FontSample key={name} name={`font.${name}`} value={value} sample={tDesign("title")} />
              ))}
              {satoriFontEntries.map(([name, value]) => (
                <FontSample key={`satori-${name}`} name={`satoriTokens.font.${name}`} value={value} sample={tDesign("title")} />
              ))}
            </div>
          </TokenSubsection>
          <TokenSubsection title={tDesign("tokens.sizeTitle")}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {fontSizeEntries.map(([name, value]) => (
                <TypographyValue key={name} name={name} value={value} style={{ fontSize: value }} sample={tDesign("title")} />
              ))}
            </div>
          </TokenSubsection>
          <TokenSubsection title={tDesign("tokens.weightTitle")}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {fontWeightEntries.map(([name, value]) => (
                <TypographyValue key={name} name={name} value={String(value)} style={{ fontWeight: value }} sample={tDesign("title")} />
              ))}
            </div>
          </TokenSubsection>
          <TokenSubsection title={tDesign("tokens.lineHeightTitle")}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {lineHeightEntries.map(([name, value]) => (
                <TypographyValue key={name} name={name} value={String(value)} style={{ lineHeight: value }} sample={tDesign("subtitle")} />
              ))}
            </div>
          </TokenSubsection>
        </div>
      </Section>

      <Section title={tDesign("tokens.spacingTitle")}>
        <div className="grid gap-2 sm:grid-cols-2">
          {spacingEntries.map(([name, value]) => (
            <SpacingToken key={name} name={name} value={value} />
          ))}
        </div>
      </Section>

      <Section title={tDesign("tokens.radiusTitle")}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {radiusEntries.map(([name, value]) => (
            <RadiusToken key={name} name={name} value={value} />
          ))}
        </div>
      </Section>

      <Section title={tDesign("tokens.shadowTitle")}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {shadowEntries.map(([name, value]) => (
            <ShadowToken key={name} name={name} value={value} />
          ))}
        </div>
      </Section>

      <Section title={tDesign("tokens.motionTitle")}>
        <div className="grid gap-4 lg:grid-cols-2">
          <TokenSubsection title={tDesign("tokens.durationTitle")}>
            <div className="space-y-2">
              {durationEntries.map(([name, value]) => (
                <MotionDurationToken key={name} name={name} value={value} />
              ))}
            </div>
          </TokenSubsection>
          <TokenSubsection title={tDesign("tokens.easingTitle")}>
            <div className="space-y-2">
              {easingEntries.map(([name, value]) => (
                <MotionEasingToken key={name} name={name} value={value} />
              ))}
            </div>
          </TokenSubsection>
        </div>
      </Section>

      {/* Badge tones */}
      <Section title="Badge — tones">
        <div className="flex flex-wrap gap-2">
          {tones.map((tone) => (
            <Badge key={tone} tone={tone}>
              {tone}
            </Badge>
          ))}
        </div>
        <h3 className="text-sm font-semibold text-fg-muted mt-4 mb-2">Outlined</h3>
        <div className="flex flex-wrap gap-2">
          {tones.map((tone) => (
            <Badge key={`o-${tone}`} tone={tone} outlined>
              {tone}
            </Badge>
          ))}
        </div>
        <h3 className="text-sm font-semibold text-fg-muted mt-4 mb-2">Sizes</h3>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" size="xs">xs</Badge>
          <Badge tone="brand" size="sm">sm</Badge>
          <Badge tone="brand" size="md">md</Badge>
        </div>
      </Section>

      {/* DateChip */}
      <Section title="DateChip">
        <h3 className="text-sm font-semibold text-fg-muted mb-2">Inline</h3>
        <div className="flex flex-wrap gap-4">
          <DateChip start={startStr} locale={locale} />
          <DateChip start={startStr} end={endStr} locale={locale} />
          <DateChip start={startStr} time="19:00" locale={locale} />
        </div>
        <h3 className="text-sm font-semibold text-fg-muted mt-4 mb-2">Stacked</h3>
        <div className="flex flex-wrap gap-4">
          <DateChip start={startStr} time="19:00" variant="stacked" locale={locale} />
          <DateChip start={startStr} end={endStr} variant="stacked" locale={locale} />
        </div>
      </Section>

      {/* FilterChip */}
      <Section title={tDesign("components.filterChipInteractiveTitle")}>
        <p className="text-xs text-fg-muted mb-2">
          {tDesign("components.filterChipInteractiveNote")}
        </p>
        <FilterChipDemo />
      </Section>

      {/* Mascot avatar */}
      <Section title="MascotAvatar">
        <div className="flex flex-wrap items-end gap-6">
          <div className="text-center">
            <MascotAvatar variant="inline" size={64} />
            <p className="text-xs text-fg-muted mt-1">inline 64</p>
          </div>
          <div className="text-center">
            <MascotAvatar variant="inline" size={96} />
            <p className="text-xs text-fg-muted mt-1">inline 96</p>
          </div>
          <div className="text-center">
            <MascotAvatar variant="framed" shape="square" size={128} />
            <p className="text-xs text-fg-muted mt-1">framed square 128</p>
          </div>
          <div className="text-center">
            <MascotAvatar variant="framed" shape="circle" size={128} />
            <p className="text-xs text-fg-muted mt-1">framed circle 128</p>
          </div>
          <div className="text-center">
            <MascotAvatar variant="inline" size={96} upright />
            <p className="text-xs text-fg-muted mt-1">upright (no tilt)</p>
          </div>
        </div>
      </Section>

      {/* Surface stack */}
      <Section title="Surface tokens">
        <div className="space-y-2">
          <div className="p-4 rounded-lg border border-line" style={{ background: "var(--color-bg)" }}>
            <code className="text-xs font-mono">--color-bg</code> — page background
          </div>
          <div className="bg-surface p-4 rounded-lg border border-line">
            <code className="text-xs font-mono">bg-surface</code> — card / panel
          </div>
          <div className="bg-elevated p-4 rounded-lg border border-line">
            <code className="text-xs font-mono">bg-elevated</code> — elevated (bg-muted also available)
          </div>
          <div className="bg-muted p-4 rounded-lg border border-line">
            <code className="text-xs font-mono">bg-muted</code> — subtle hover / secondary
          </div>
        </div>
      </Section>

      <footer className="text-xs text-fg-muted text-center pt-6 border-t border-line">
        {tDesign("footer")}
      </footer>
      </div>
    </div>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-display font-bold text-fg border-b border-line pb-1">
        {title}
      </h2>
      {description ? <p className="max-w-3xl text-sm leading-relaxed text-fg-muted">{description}</p> : null}
      <div>{children}</div>
    </section>
  );
}

function TokenIndexItem({ label, count }: { label: string; count: number }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="text-sm font-semibold text-fg">{label}</div>
      <div className="mt-1 font-mono text-xs text-fg-muted">{count}</div>
    </div>
  );
}

function TokenSubsection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="font-display text-base font-bold text-fg">{title}</h3>
      {children}
    </div>
  );
}

function GradientSwatch({ name, stops }: { name: string; stops: string[] }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div
        className="h-16 rounded-lg border border-line"
        style={{ background: `linear-gradient(90deg, ${stops.join(", ")})` }}
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <code className="font-mono text-xs text-fg">{name}</code>
        {stops.map((stop) => (
          <span key={stop} className="rounded-full border border-line bg-bg px-2 py-0.5 font-mono text-[11px] text-fg-muted">
            {stop}
          </span>
        ))}
      </div>
    </div>
  );
}

function FontSample({ name, value, sample }: { name: string; value: string; sample: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="font-mono text-xs text-fg-muted">{name}</div>
      <div className="mt-1 truncate text-lg text-fg" style={{ fontFamily: value }}>
        {sample}
      </div>
      <div className="mt-1 truncate font-mono text-[11px] text-fg-muted">{value}</div>
    </div>
  );
}

function TypographyValue({
  name,
  value,
  sample,
  style,
}: {
  name: string;
  value: string;
  sample: string;
  style: React.CSSProperties;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="flex items-baseline justify-between gap-2">
        <code className="font-mono text-xs text-fg">{name}</code>
        <code className="font-mono text-[11px] text-fg-muted">{value}</code>
      </div>
      <div className="mt-2 line-clamp-3 text-fg" style={style}>
        {sample}
      </div>
    </div>
  );
}

function SpacingToken({ name, value }: { name: string; value: string }) {
  const barWidth = value === "0" ? "1px" : value;
  return (
    <div className="grid grid-cols-[4rem_1fr_4rem] items-center gap-3 rounded-lg border border-line bg-surface p-3">
      <code className="font-mono text-xs text-fg">{name}</code>
      <div className="h-3 rounded-full bg-muted">
        <div className="h-3 rounded-full bg-mascot-red" style={{ width: barWidth }} />
      </div>
      <code className="text-right font-mono text-xs text-fg-muted">{value}</code>
    </div>
  );
}

function RadiusToken({ name, value }: { name: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="h-16 border border-line bg-bg" style={{ borderRadius: value }} />
      <div className="mt-2 flex items-center justify-between gap-2">
        <code className="font-mono text-xs text-fg">{name}</code>
        <code className="font-mono text-[11px] text-fg-muted">{value}</code>
      </div>
    </div>
  );
}

function ShadowToken({ name, value }: { name: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="h-16 rounded-lg border border-line bg-bg" style={{ boxShadow: value }} />
      <div className="mt-2 space-y-1">
        <code className="font-mono text-xs text-fg">{name}</code>
        <div className="break-all font-mono text-[11px] text-fg-muted">{value}</div>
      </div>
    </div>
  );
}

function MotionDurationToken({ name, value }: { name: string; value: number }) {
  return (
    <div className="group rounded-lg border border-line bg-surface p-3">
      <div className="flex items-center justify-between gap-3">
        <code className="font-mono text-xs text-fg">{name}</code>
        <code className="font-mono text-xs text-fg-muted">{value}ms</code>
      </div>
      <div className="mt-3 h-2 rounded-full bg-muted">
        <div
          className="h-2 w-8 rounded-full bg-mascot-red motion-reduce:transition-none group-hover:translate-x-16"
          style={{ transitionDuration: `${value}ms`, transitionProperty: "transform" }}
        />
      </div>
    </div>
  );
}

function MotionEasingToken({ name, value }: { name: string; value: string }) {
  return (
    <div className="group rounded-lg border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <code className="font-mono text-xs text-fg">{name}</code>
        <code className="font-mono text-[11px] text-fg-muted">{value}</code>
      </div>
      <div className="mt-3 h-2 rounded-full bg-muted">
        <div
          className="h-2 w-8 rounded-full bg-mascot-leaf motion-reduce:transition-none group-hover:translate-x-16"
          style={{ transitionDuration: "320ms", transitionTimingFunction: value, transitionProperty: "transform" }}
        />
      </div>
    </div>
  );
}

function Swatch({ name, value }: { name: string; value: string }) {
  return (
    <div className="rounded-lg border border-line overflow-hidden">
      <div style={{ height: "4rem", background: value }} />
      <div className="p-2 bg-surface text-xs">
        <div className="font-mono text-fg">{name}</div>
        <div className="font-mono text-fg-muted">{value}</div>
      </div>
    </div>
  );
}
