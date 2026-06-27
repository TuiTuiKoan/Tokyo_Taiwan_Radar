import { useTranslations } from "next-intl";

interface Props {
  rawTitle: string | null;
  rawDescription: string | null;
  selectionReason: string | null;
  locale: string;
  reportSection?: React.ReactNode;
  hideSelectionReason?: boolean;
}

function parseSelectionReason(raw: string | null, locale: string): string | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      const map = parsed as Record<string, string>;
      return map[locale] || map["ja"] || null;
    }
  } catch {
    // legacy: plain string (Japanese only)
  }
  return raw;
}

export default function RawDataSection({ rawTitle, rawDescription, selectionReason, locale, reportSection, hideSelectionReason }: Props) {
  const t = useTranslations("event");

  if (!selectionReason && !reportSection) return null;

  const displayedReason = parseSelectionReason(selectionReason, locale);

  // 人工創建活動（user_submission / manual）沒有 AI 選別理由：略過 amber 框，僅保留報錯按鈕
  if (hideSelectionReason) {
    return reportSection ? <div className="mb-8">{reportSection}</div> : null;
  }

  return (
    <div className="mb-8">
      {/* Selection Reason + Report button (always together) */}
      <div className="border border-amber-200 bg-amber-50 rounded-xl p-4 dark:border-amber-800/50 dark:bg-amber-900/50">
        <h2 className="text-sm font-medium text-amber-700 mb-1">{t("selectionReason")}</h2>
        {displayedReason && (
          <p className="text-sm text-amber-900 mb-3">{displayedReason}</p>
        )}
        {reportSection}
      </div>
    </div>
  );
}
