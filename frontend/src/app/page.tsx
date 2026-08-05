import { SecurityPattern } from "@/components/SecurityPattern";
import { DownloaderLazy } from "@/components/DownloaderLazy";
import { SitePresence } from "@/components/SitePresence";
import { SiteFooter } from "@/components/SiteFooter";
import { JsonLd } from "@/components/JsonLd";
import { BRAND_NAME, BRAND_URL } from "@/lib/brand";

export default function Home() {
  return (
    <main id="main-content" className="relative z-10 flex flex-1 flex-col">
      <JsonLd />
      <SecurityPattern />
      <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-col gap-8 px-5 pb-16 pt-10 sm:px-8 sm:pt-14">
        <header className="text-left">
          <h1 className="brand-rainbow text-5xl font-extrabold leading-none tracking-tight sm:text-7xl">
            <a
              href={BRAND_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:opacity-90"
            >
              {BRAND_NAME}
            </a>
          </h1>
          <p className="mt-4 text-lg font-semibold tracking-tight text-[var(--ink)] sm:text-xl">
            影片與字幕下載
          </p>
          <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-[var(--ink-soft)]">
            支援 YouTube、Facebook、Instagram。
          </p>
          <p className="mt-3 text-[15px] leading-relaxed text-[var(--ink-soft)]">
            官方網站{" "}
            <a
              href={BRAND_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="break-all font-semibold text-[var(--accent)] underline-offset-4 hover:underline"
            >
              https://www.getzenithmind.com/zh-TW
            </a>
          </p>
          <SitePresence />
        </header>

        <DownloaderLazy />

        <SiteFooter />
      </div>
    </main>
  );
}
