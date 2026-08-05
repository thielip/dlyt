export const BRAND_NAME = "巔峰思維";
export const BRAND_URL = "https://www.getzenithmind.com/zh-TW";
export const BRAND_EMAIL = "privacy@getzenithmind.com";

export const CONSENT_KEY = "zenith.cookieConsent";
export type ConsentChoice = "accepted" | "essential";

export function readConsent(): ConsentChoice | null {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(CONSENT_KEY);
    if (v === "accepted" || v === "essential") return v;
  } catch {
    /* ignore */
  }
  return null;
}

export function writeConsent(choice: ConsentChoice): void {
  try {
    localStorage.setItem(CONSENT_KEY, choice);
    window.dispatchEvent(new Event("zenith-consent"));
  } catch {
    /* ignore */
  }
}

export function analyticsAllowed(): boolean {
  return readConsent() === "accepted";
}
