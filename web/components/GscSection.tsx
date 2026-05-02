"use client";

import { useEffect, useState } from "react";

interface GscData {
  configured: boolean;
  error?: string;
  period?: { startDate: string; endDate: string };
  indexedPages?: number;
  totalClicks?: number;
  totalImpressions?: number;
  topQueries?: Array<{
    query: string;
    clicks: number;
    impressions: number;
    ctr: number;
    position: number;
  }>;
}

export default function GscSection() {
  const [data, setData] = useState<GscData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/admin/gsc")
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(() => setData({ configured: false, error: "fetch failed" }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Google Search Console（28 天）</h2>
        <p className="text-sm text-gray-400 animate-pulse">載入中…</p>
      </section>
    );
  }

  if (!data?.configured) {
    return (
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Google Search Console（28 天）</h2>
        <div className="border border-dashed rounded-lg p-4 text-sm text-gray-500 space-y-2">
          <p className="font-medium text-gray-700">尚未設定 GSC API 憑證</p>
          <p>請在 Vercel 環境變數中設定以下三項後重新部署：</p>
          <ul className="list-disc ml-5 space-y-1 font-mono text-xs">
            <li>GSC_SERVICE_ACCOUNT_EMAIL</li>
            <li>GSC_SERVICE_ACCOUNT_KEY（PEM，換行符號用 \n）</li>
            <li>GSC_SITE_URL（e.g. https://tokyotaiwanradar.com/）</li>
          </ul>
          <p className="text-xs text-gray-400">
            步驟：Google Cloud Console → 建立服務帳號 → 下載 JSON Key →
            在 Search Console 新增該帳號（限制權限）→ 填入以上三個環境變數
          </p>
        </div>
      </section>
    );
  }

  if (data.error) {
    return (
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Google Search Console（28 天）</h2>
        <p className="text-sm text-red-500">API 錯誤：{data.error}</p>
      </section>
    );
  }

  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold mb-3">
        Google Search Console（{data.period?.startDate} — {data.period?.endDate}）
      </h2>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="border rounded-lg p-3 bg-white">
          <div className="text-xs text-gray-500 mb-1">已索引頁面</div>
          <div className="text-2xl font-bold tabular-nums">{(data.indexedPages ?? 0).toLocaleString()}</div>
        </div>
        <div className="border rounded-lg p-3 bg-white">
          <div className="text-xs text-gray-500 mb-1">總點擊數</div>
          <div className="text-2xl font-bold tabular-nums">{(data.totalClicks ?? 0).toLocaleString()}</div>
        </div>
        <div className="border rounded-lg p-3 bg-white">
          <div className="text-xs text-gray-500 mb-1">總曝光數</div>
          <div className="text-2xl font-bold tabular-nums">{(data.totalImpressions ?? 0).toLocaleString()}</div>
        </div>
      </div>

      {/* Top queries table */}
      {data.topQueries && data.topQueries.length > 0 && (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-gray-500">
              <tr>
                <th className="px-3 py-2">關鍵字</th>
                <th className="px-3 py-2 text-right">點擊</th>
                <th className="px-3 py-2 text-right">曝光</th>
                <th className="px-3 py-2 text-right">CTR%</th>
                <th className="px-3 py-2 text-right">平均排名</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.topQueries.map((q) => (
                <tr key={q.query} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium max-w-xs truncate">{q.query}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{q.clicks}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{q.impressions.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{q.ctr}%</td>
                  <td className="px-3 py-2 text-right tabular-nums">{q.position}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
