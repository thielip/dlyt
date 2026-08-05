import Link from "next/link";
import type { Metadata } from "next";
import { SecurityPattern } from "@/components/SecurityPattern";
import { BRAND_NAME, BRAND_URL } from "@/lib/brand";

export const metadata: Metadata = {
  title: "免責聲明",
  description: `${BRAND_NAME} 服務使用條款與免責說明。`,
  alternates: { canonical: "/disclaimer" },
};

export default function DisclaimerPage() {
  return (
    <main id="main-content" className="relative z-10 mx-auto flex w-full max-w-2xl flex-col gap-6 px-5 py-12 sm:px-8">
      <SecurityPattern />
      <div className="relative z-10">
        <p className="brand-rainbow text-4xl font-extrabold tracking-tight">
          <a href={BRAND_URL} target="_blank" rel="noopener noreferrer">
            {BRAND_NAME}
          </a>
        </p>
        <h1 className="mt-4 text-2xl font-semibold text-[var(--ink)]">免責聲明</h1>
        <div className="panel-glass rainbow-border mt-6 space-y-4 rounded-2xl border border-[var(--border)] p-5 text-[15px] leading-relaxed text-[var(--ink-soft)] sm:p-7">
          <p>
            本服務僅供個人學習與技術研究。請自行確認下載內容是否符合 YouTube
            服務條款、著作權法與當地法規。
          </p>
          <p>
            我們不保證服務可用性、下載成功率或檔案完整性。雲端免費方案有頻寬與用量限制，可能隨時維護或下線。
          </p>
          <p>
            使用者應對自己的行為負責。若權利人提出申訴，營運者可能暫停服務（含一鍵維護模式）。
          </p>
          <p className="text-sm text-[var(--muted)]">
            建議優先選擇標示「直連」的畫質，讓檔案流量不經本站伺服器。個資與 Cookie
            說明請見{" "}
            <Link href="/privacy" className="text-[var(--accent)] underline underline-offset-2">
              隱私權政策
            </Link>
            。
          </p>
        </div>
        <div className="mt-8 flex flex-wrap gap-4 text-sm font-semibold">
          <Link href="/" className="text-[var(--accent)] hover:underline">
            ← 返回下載頁
          </Link>
          <Link href="/privacy" className="text-[var(--accent)] hover:underline">
            隱私權政策
          </Link>
        </div>
      </div>
    </main>
  );
}
