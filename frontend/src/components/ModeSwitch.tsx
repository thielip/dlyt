"use client";

import type { DownloadMode } from "@/lib/types";

type UiMode = Exclude<DownloadMode, "asr">;

interface ModeSwitchProps {
  mode: UiMode;
  onChange: (mode: UiMode) => void;
  disabled?: boolean;
}

const OPTIONS: { value: UiMode; label: string; hint: string }[] = [
  { value: "video", label: "下載影片", hint: "預設 360p 直連；進階需密碼" },
  { value: "subtitle", label: "僅下載字幕", hint: "輸出 SRT / VTT / TXT" },
];

export function ModeSwitch({ mode, onChange, disabled }: ModeSwitchProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {OPTIONS.map((option) => {
        const active = mode === option.value;
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`rounded-xl border px-4 py-3 text-left transition-all disabled:cursor-not-allowed disabled:opacity-60 ${
              active
                ? "rainbow-border border-transparent bg-[var(--accent-soft)]"
                : "border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--border-strong)]"
            }`}
          >
            <span className="block text-[15px] font-semibold text-[var(--ink)]">
              {option.label}
            </span>
            <span className="mt-0.5 block text-sm text-[var(--muted)]">
              {option.hint}
            </span>
          </button>
        );
      })}
    </div>
  );
}
