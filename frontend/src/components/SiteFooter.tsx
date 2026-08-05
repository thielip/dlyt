import Link from "next/link";
import { BRAND_NAME, BRAND_URL } from "@/lib/brand";

export function SiteFooter() {
  return (
    <footer className="flex flex-col gap-3 text-center text-xs text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between sm:text-left">
      <p>
        © {BRAND_NAME} · 請優先選「直連」畫質。
      </p>
      <nav
        className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 sm:justify-end"
        aria-label="法律與相關連結"
      >
        <Link href="/disclaimer" className="underline underline-offset-2">
          免責聲明
        </Link>
        <Link href="/privacy" className="underline underline-offset-2">
          隱私權政策
        </Link>
        <a
          href={BRAND_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono underline-offset-2 hover:underline"
        >
          getzenithmind.com
        </a>
      </nav>
    </footer>
  );
}
