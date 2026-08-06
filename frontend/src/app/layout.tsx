import type { Metadata, Viewport } from "next";
import { Cormorant_Garamond, DM_Sans } from "next/font/google";
import { CookieConsent } from "@/components/CookieConsent";
import "./globals.css";

const display = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-display-face",
  display: "swap",
});

const body = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body-face",
  display: "swap",
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ||
  "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "巔峰思維｜YouTube／FB／IG 影片與字幕下載",
    template: "%s · 巔峰思維",
  },
  description:
    "巔峰思維：貼上 YouTube、Facebook 或 Instagram 網址，選擇畫質或字幕，完成後直接下載。",
  applicationName: "巔峰思維",
  authors: [{ name: "巔峰思維", url: "https://www.getzenithmind.com/zh-TW" }],
  creator: "巔峰思維",
  publisher: "巔峰思維",
  keywords: [
    "巔峰思維",
    "Zenith Mind",
    "YouTube 下載",
    "字幕下載",
    "Facebook 影片",
    "Instagram 影片",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "zh_TW",
    url: "/",
    siteName: "巔峰思維",
    title: "巔峰思維｜影片與字幕下載",
    description:
      "貼上 YouTube、Facebook 或 Instagram 網址，選擇畫質或字幕後下載。",
  },
  twitter: {
    card: "summary",
    title: "巔峰思維｜影片與字幕下載",
    description: "貼上 YouTube、Facebook 或 Instagram 網址即可下載。",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f1ef" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0b" },
  ],
  colorScheme: "light dark",
};

const themeBootScript = `
(function(){
  try {
    var t = localStorage.getItem('dlyt-theme');
    if (t !== 'light' && t !== 'dark') t = 'light';
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="zh-Hant"
      data-theme="light"
      suppressHydrationWarning
      className={`h-full antialiased ${display.variable} ${body.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="relative flex min-h-full flex-col">
        <a href="#main-content" className="skip-link">
          跳到主要內容
        </a>
        {children}
        <CookieConsent />
      </body>
    </html>
  );
}
