import Link from "next/link";
import type { Metadata } from "next";
import { SecurityPattern } from "@/components/SecurityPattern";
import { BRAND_NAME, BRAND_URL, BRAND_EMAIL } from "@/lib/brand";

export const metadata: Metadata = {
  title: "隱私權政策",
  description: `${BRAND_NAME} 隱私權政策：說明本服務如何處理本機儲存、瀏覽統計與個人資料。`,
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  const updated = "2026-08-05";

  return (
    <main
      id="main-content"
      className="relative z-10 mx-auto flex w-full max-w-2xl flex-col gap-6 px-5 py-12 sm:px-8"
    >
      <SecurityPattern />
      <div className="relative z-10">
        <p className="brand-display text-4xl sm:text-5xl">
          <a href={BRAND_URL} target="_blank" rel="noopener noreferrer">
            {BRAND_NAME}
          </a>
        </p>
        <h1 className="mt-4 text-2xl font-medium text-[var(--ink)]">
          隱私權政策
        </h1>
        <p className="mt-2 text-sm text-[var(--muted)]">最後更新日期：{updated}</p>

        <div className="hairline-panel mt-6 space-y-5 border border-[var(--border)] p-5 text-[15px] leading-relaxed text-[var(--ink-soft)] sm:p-7">
          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">1. 總則</h2>
            <p className="mt-2">
              {BRAND_NAME}
              （以下稱「我們」）重視您的隱私。本政策說明本網站（影片／字幕下載工具）如何蒐集、使用與保護相關資訊，並參考台灣《個人資料保護法》及歐盟
              GDPR 之精神撰寫。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">
              2. 我們蒐集哪些資料
            </h2>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>
                <strong className="text-[var(--ink)]">必要本機資料：</strong>
                主題（深／淺色）偏好，存於瀏覽器 localStorage，僅用於介面顯示。
              </li>
              <li>
                <strong className="text-[var(--ink)]">統計用匿名識別（需您同意）：</strong>
                隨機產生的訪客 ID，用於即時線上人數與瀏覽次數統計，不含姓名、電子郵件或精確定位。
              </li>
              <li>
                <strong className="text-[var(--ink)]">您主動提供的內容：</strong>
                貼上的影片網址、選擇的畫質／字幕選項；若使用語音辨識，您自行提供的
                Gemini API Key 僅隨該次請求傳送至 Google，我們不會存入伺服器資料庫。
              </li>
              <li>
                <strong className="text-[var(--ink)]">技術紀錄：</strong>
                伺服器可能短暫保留下載任務狀態與錯誤日誌，用於維運與除錯，並依設定定期清除。
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">3. 使用目的</h2>
            <p className="mt-2">
              提供下載與字幕功能、維護服務穩定、統計匿名使用量，以及改善使用者體驗。我們不會出售您的個人資料。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">
              4. Cookie 與本機儲存
            </h2>
            <p className="mt-2">
              本站主要使用瀏覽器本機儲存（localStorage／sessionStorage），而非廣告追蹤
              Cookie。首次造訪時您可選擇「僅必要功能」或「全部允許」。拒絕統計時，我們不會寫入訪客
              ID，也不會回報瀏覽統計。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">5. 第三方服務</h2>
            <p className="mt-2">
              下載過程可能連線至 YouTube／Facebook／Instagram 等平台取得公開內容；語音辨識會使用
              Google Gemini（僅在您提供金鑰時）。請一併參閱各平台隱私政策。託管環境（如
              Vercel、Render）可能依其服務條款處理連線紀錄。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">6. 資料保存與安全</h2>
            <p className="mt-2">
              傳輸建議透過 HTTPS。任務檔案與暫存資料會依系統設定自動刪除。我們採合理技術與組織措施降低未授權存取風險，但無法保證絕對安全。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">7. 您的權利</h2>
            <p className="mt-2">
              您可清除瀏覽器本機資料、改選「僅必要功能」，或以無痕模式使用本站。若您認為我們持有與您相關之個人資料，可來信行使查詢、更正或刪除等權利（以適用法律為準）。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">8. 聯絡方式</h2>
            <p className="mt-2">
              品牌網站：{" "}
              <a
                href={BRAND_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--accent)] underline underline-offset-2"
              >
                {BRAND_URL}
              </a>
              <br />
              隱私相關來信：{" "}
              <a
                href={`mailto:${BRAND_EMAIL}`}
                className="text-[var(--accent)] underline underline-offset-2"
              >
                {BRAND_EMAIL}
              </a>
              （請改為您實際收件信箱後再公開）
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[var(--ink)]">9. 政策更新</h2>
            <p className="mt-2">
              我們可能不定期更新本政策，更新後將公告於本頁並調整「最後更新日期」。繼續使用本服務即表示您知悉更新後之內容。
            </p>
          </section>
        </div>

        <div className="mt-8 flex flex-wrap gap-4 text-sm font-semibold">
          <Link href="/" className="text-[var(--accent)] hover:underline">
            ← 返回下載頁
          </Link>
          <Link href="/disclaimer" className="text-[var(--accent)] hover:underline">
            免責聲明
          </Link>
        </div>
      </div>
    </main>
  );
}
