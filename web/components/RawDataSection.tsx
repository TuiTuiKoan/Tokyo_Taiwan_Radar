import { useTranslations } from "next-intl";

interface Props {
  rawTitle: string | null;
  rawDescription: string | null;
  selectionReason: string | null;
}

export default function RawDataSection({ rawTitle, rawDescription, selectionReason }: Props) {
  const t = useTranslations("event");

  if (!rawTitle && !rawDescription && !selectionReason) return null;

  return (
    <div className="mb-8">
      {/* Selection Reason */}
      {selectionReason && (
        <div className="mb-4 border border-amber-200 bg-amber-50 rounded-xl p-4">
          <h2 className="text-sm font-medium text-amber-700 mb-1">{t("selectionReason")}</h2>
          <p className="text-sm text-amber-900">{selectionReason}</p>
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
