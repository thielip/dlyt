import { BRAND_NAME, BRAND_URL } from "@/lib/brand";

/**
 * Schema.org JSON-LD for Organization + WebApplication.
 */
export function JsonLd() {
  const siteUrl =
    process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ||
    "http://localhost:3000";

  const data = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${BRAND_URL}#organization`,
        name: BRAND_NAME,
        url: BRAND_URL,
        sameAs: [BRAND_URL],
      },
      {
        "@type": "WebSite",
        "@id": `${siteUrl}/#website`,
        url: siteUrl,
        name: `${BRAND_NAME}｜影片與字幕下載`,
        description:
          "貼上 YouTube、Facebook 或 Instagram 網址，選擇畫質或字幕後下載。",
        publisher: { "@id": `${BRAND_URL}#organization` },
        inLanguage: "zh-Hant",
      },
      {
        "@type": "WebApplication",
        "@id": `${siteUrl}/#app`,
        name: `${BRAND_NAME} 影片下載工具`,
        url: siteUrl,
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Any",
        browserRequirements: "Requires JavaScript",
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "TWD",
        },
        publisher: { "@id": `${BRAND_URL}#organization` },
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
