/**
 * Unified card-link hover — matches the navbar hamburger menu pattern.
 *
 * Default bg: bg-paper (dark mode: dark paper via CSS var)
 * Light hover: bg-[#F7FFE8] (matcha) + text-[#1F5E2B] (forest green)
 * Dark hover:  bg-green-900/40            + text-green-400
 *
 * Usage:
 *   import { CARD_LINK, CARD_LINK_ARROW } from "@/lib/classNames";
 *
 *   <Link className={`${CARD_LINK} px-4 py-3 gap-3`}>
 *     <span>Title</span>
 *     <span className={CARD_LINK_ARROW}>↗</span>
 *   </Link>
 *
 * CARD_LINK already includes `group`, `bg-paper`, and `transition` — do not add them again.
 * Use a unified container: `border border-line rounded-xl overflow-hidden divide-y divide-line`
 * Extra padding / gap / text-size go AFTER the template literal interpolation.
 */
export const CARD_LINK =
  "group flex items-center transition bg-paper dark:bg-paper hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400";

/** Arrow / chevron at the trailing edge of a CARD_LINK row. */
export const CARD_LINK_ARROW =
  "text-fg-subtle group-hover:text-[#1F5E2B] dark:group-hover:text-green-400 shrink-0";
