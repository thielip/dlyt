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
      <div className="relative z-10 mx-auto flex w-full max-w-2xl flex-col px-6 pb-20 pt-14 sm:px-10 sm:pt-20">
        <header className="gallery-enter text-left">
          <h1 className="brand-display text-5xl leading-[1.05] sm:text-7xl">
            <a
              href={BRAND_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="transition-opacity hover:opacity-70"
            >
              {BRAND_NAME}
            </a>
          </h1>
          <div className="gallery-rule mt-8 max-w-[12rem]" aria-hidden />
          <p className="gallery-enter-delay mt-8 max-w-md text-base leading-relaxed text-[var(--ink-soft)] sm:text-lg">
            影片與字幕下載。支援 YouTube、Facebook、Instagram。
          </p>
          <SitePresence />
        </header>

        <div className="gallery-enter-delay mt-14">
          <DownloaderLazy />
        </div>

        <div className="mt-20">
          <SiteFooter />
        </div>
      </div>
    </main>
  );
}
