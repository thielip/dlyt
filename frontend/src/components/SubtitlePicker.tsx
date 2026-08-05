"use client";

import type { AsrLanguage, SubtitleFormat, SubtitleTrack } from "@/lib/types";

interface SubtitlePickerProps {
  tracks: SubtitleTrack[];
  language: string;
  format: SubtitleFormat;
  onLanguageChange: (language: string) => void;
  onFormatChange: (format: SubtitleFormat) => void;
  geminiApiKey: string;
  onGeminiApiKeyChange: (key: string) => void;
  asrLanguage: AsrLanguage;
  onAsrLanguageChange: (language: AsrLanguage) => void;
  onSwitchToVideo?: () => void;
  disabled?: boolean;
}

const FORMATS: { value: SubtitleFormat; label: string; hint: string }[] = [
  { value: "srt", label: "SRT", hint: "最常見，多數播放器支援" },
  { value: "vtt", label: "VTT", hint: "網頁影片標準格式" },
  { value: "txt", label: "TXT", hint: "純文字，方便複製閱讀" },
];

const ASR_LANGS: { value: AsrLanguage; label: string }[] = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "auto", label: "自動偵測" },
];

export function SubtitlePicker({
  tracks,
  language,
  format,
  onLanguageChange,
  onFormatChange,
  geminiApiKey,
  onGeminiApiKeyChange,
  asrLanguage,
  onAsrLanguageChange,
  onSwitchToVideo,
  disabled,
}: SubtitlePickerProps) {
  if (tracks.length === 0) {
    return (
      <div className="flex flex-col gap-5">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-4 text-sm text-[var(--ink-soft)]">
          <p className="font-semibold text-[var(--ink)]">這支影片沒有可用字幕</p>
          <p className="mt-2 leading-relaxed text-[var(--muted)]">
            YouTube 未提供可下載的字幕軌（含自動產生字幕）。畫面上的歌詞或燒錄字幕無法抓取。
            可用你的 Gemini API Key 透過語音辨識產生字幕，或改下載影片。
          </p>
          {onSwitchToVideo && (
            <button
              type="button"
              disabled={disabled}
              onClick={onSwitchToVideo}
              className="btn-ink mt-4 inline-flex min-h-10 items-center justify-center rounded-lg px-4 text-sm font-semibold disabled:opacity-50"
            >
              改為下載影片
            </button>
          )}
        </div>

        <fieldset disabled={disabled} className="flex flex-col gap-4">
          <legend className="text-sm font-semibold text-[var(--ink-soft)]">
            語音辨識產生字幕（Gemini）
          </legend>
          <div>
            <label
              htmlFor="gemini-api-key"
              className="mb-2 block text-sm font-medium text-[var(--ink-soft)]"
            >
              Gemini API Key
            </label>
            <input
              id="gemini-api-key"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={geminiApiKey}
              onChange={(e) => onGeminiApiKeyChange(e.target.value)}
              placeholder="貼上你的 Google AI Studio API Key"
              className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 text-[15px] text-[var(--ink)] outline-none placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:shadow-[0_0_0_4px_var(--ring)]"
            />
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
              金鑰只用於本次請求呼叫 Google Gemini，不會存進資料庫。可至{" "}
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noreferrer"
                className="underline underline-offset-2"
              >
                Google AI Studio
              </a>{" "}
              免費建立。
            </p>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-[var(--ink-soft)]">辨識語言</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {ASR_LANGS.map((item) => {
                const active = asrLanguage === item.value;
                return (
                  <label
                    key={item.value}
                    className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-sm ${
                      active
                        ? "rainbow-border border-transparent bg-[var(--surface-2)]"
                        : "border-[var(--border)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="asr-language"
                      value={item.value}
                      checked={active}
                      onChange={() => onAsrLanguageChange(item.value)}
                      className="accent-[var(--accent)]"
                    />
                    {item.label}
                  </label>
                );
              })}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-[var(--ink-soft)]">輸出格式</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {FORMATS.map((item) => {
                const active = format === item.value;
                return (
                  <label
                    key={item.value}
                    className={`flex cursor-pointer flex-col rounded-xl border px-4 py-3 ${
                      active
                        ? "rainbow-border border-transparent bg-[var(--accent-soft)]"
                        : "border-[var(--border)]"
                    }`}
                  >
                    <span className="inline-flex items-center gap-2">
                      <input
                        type="radio"
                        name="asr-subtitle-format"
                        value={item.value}
                        checked={active}
                        onChange={() => onFormatChange(item.value)}
                        className="accent-[var(--accent)]"
                      />
                      <span className="font-mono text-sm font-semibold uppercase">
                        {item.label}
                      </span>
                    </span>
                    <span className="mt-1 pl-6 text-xs text-[var(--muted)]">{item.hint}</span>
                  </label>
                );
              })}
            </div>
          </div>
        </fieldset>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <fieldset disabled={disabled}>
        <legend className="mb-3 text-sm font-semibold text-[var(--ink-soft)]">
          字幕語言
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {tracks.map((track) => {
            const active = language === track.language;
            return (
              <label
                key={track.language}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition-colors ${
                  active
                    ? "rainbow-border border-transparent bg-[var(--surface-2)]"
                    : "border-[var(--border)] hover:border-[var(--border-strong)]"
                } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <input
                  type="radio"
                  name="subtitle-language"
                  value={track.language}
                  checked={active}
                  onChange={() => onLanguageChange(track.language)}
                  className="accent-[var(--accent)]"
                />
                <span>
                  <span className="block text-[15px] font-semibold text-[var(--ink)]">
                    {track.languageName}
                  </span>
                  <span className="mt-0.5 block text-sm text-[var(--muted)]">
                    {track.language}
                    {track.isAutoGenerated ? " · 自動產生" : ""}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset disabled={disabled}>
        <legend className="mb-3 text-sm font-semibold text-[var(--ink-soft)]">
          輸出格式
        </legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {FORMATS.map((item) => {
            const active = format === item.value;
            return (
              <label
                key={item.value}
                className={`flex cursor-pointer flex-col rounded-xl border px-4 py-3 transition-colors ${
                  active
                    ? "rainbow-border border-transparent bg-[var(--accent-soft)]"
                    : "border-[var(--border)] hover:border-[var(--border-strong)]"
                } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <span className="inline-flex items-center gap-2">
                  <input
                    type="radio"
                    name="subtitle-format"
                    value={item.value}
                    checked={active}
                    onChange={() => onFormatChange(item.value)}
                    className="accent-[var(--accent)]"
                  />
                  <span className="font-mono text-sm font-semibold uppercase text-[var(--ink)]">
                    {item.label}
                  </span>
                </span>
                <span className="mt-1 pl-6 text-xs leading-relaxed text-[var(--muted)]">
                  {item.hint}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}
