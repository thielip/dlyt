import Link from "next/link";
import { BRAND_NAME, BRAND_URL } from "@/lib/brand";

export function SiteFooter() {
  return (
    <footer className="flex flex-col gap-4 border-t border-[var(--hairline)] pt-8 text-xs tracking-wide text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
      <p>
        © {BRAND_NAME}
      </p>
      <nav
        className="flex flex-wrap items-center gap-x-5 gap-y-2"
        aria-label="法律與相關連結"
      >
        <Link
          href="/disclaimer"
          className="underline-offset-4 transition-opacity hover:text-[var(--ink)] hover:underline"
        >
          免責聲明
        </Link>
        <Link
          href="/privacy"
          className="underline-offset-4 transition-opacity hover:text-[var(--ink)] hover:underline"
        >
          隱私權政策
        </Link>
        <a
          href={BRAND_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-4 transition-opacity hover:text-[var(--ink)] hover:underline"
        >
          getzenithmind.com
        </a>
      </nav>
    </footer>
  );
}
