import { useTranslations } from "next-intl";

interface Props {
  rawTitle: string | null;
  rawDescription: string | null;
  selectionReason: string | null;
  locale: string;
  reportSection?: React.ReactNode;
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

export default function RawDataSection({ rawTitle, rawDescription, selectionReason, locale, reportSection }: Props) {
  const t = useTranslations("event");

  if (!rawTitle && !rawDescription && !selectionReason) return null;

  const displayedReason = parseSelectionReason(selectionReason, locale);

  return (
    <div className="mb-8">
      {/* Selection Reason */}
      {displayedReason && (
        <div className="mb-4 border border-amber-200 bg-amber-50 rounded-xl p-4">
          <h2 className="text-sm font-medium text-amber-700 mb-1">{t("selectionReason")}</h2>
          <p className="text-sm text-amber-900">{displayedReason}</p>
          {reportSection}
        </div>
      )}

      {/* Raw Data */}
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 text-sm text-gray-400 font-medium border-b border-gray-100">
          {t("rawData")}
        </div>
        <div className="px-4 pb-4 max-h-[600px] overflow-y-auto">
          {rawTitle && (
            <div className="mt-3">
              <h3 className="text-xs text-gray-400 mb-1">{t("rawTitle")}</h3>
              <p className="text-sm text-gray-600">{rawTitle}</p>
            </div>
          )}
          {rawDescription && (
            <div className="mt-3">
              <h3 className="text-xs text-gray-400 mb-1">{t("rawDescription")}</h3>
              <p className="whitespace-pre-wrap text-sm text-gray-600">
                {rawDescription}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
