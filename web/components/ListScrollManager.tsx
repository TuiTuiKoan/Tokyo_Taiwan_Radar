"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

export default function ListScrollManager() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // On mount: restore scroll position
  useEffect(() => {
    // Priority 1: locale switch scroll restore
    const localeScroll = sessionStorage.getItem("ttr_locale_scroll");
    if (localeScroll) {
      sessionStorage.removeItem("ttr_locale_scroll");
      const y = parseInt(localeScroll, 10);
      if (!isNaN(y)) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            window.scrollTo({ top: y, behavior: "instant" });
          });
        });
      }
      return;
    }

    // Priority 2: back-from-detail scroll restore
    const listScroll = sessionStorage.getItem("ttr_list_scroll");
    if (listScroll) {
      try {
        const { url, y } = JSON.parse(listScroll);
        const currentUrl = pathname + (searchParams.toString() ? "?" + searchParams.toString() : "");
        if (url === currentUrl && typeof y === "number") {
          sessionStorage.removeItem("ttr_list_scroll");
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              window.scrollTo({ top: y, behavior: "instant" });
            });
          });
        }
      } catch {
        sessionStorage.removeItem("ttr_list_scroll");
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save scroll position before navigating to event detail
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      const anchor = target.closest("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href") ?? "";
      // Match /[locale]/events/[id] but not admin paths
      if (/\/events\/[^/]+$/.test(href) && !href.includes("/admin")) {
        const currentUrl = pathname + (searchParams.toString() ? "?" + searchParams.toString() : "");
        sessionStorage.setItem(
          "ttr_list_scroll",
          JSON.stringify({ url: currentUrl, y: window.scrollY })
        );
      }
    }
    document.addEventListener("click", handleClick, true);
    return () => document.removeEventListener("click", handleClick, true);
  }, [pathname, searchParams]);

  return null;
}
