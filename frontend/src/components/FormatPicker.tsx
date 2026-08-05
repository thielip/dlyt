"use client";

import { useMemo, useState } from "react";
import type { VideoFormat } from "@/lib/types";
import { formatBytes } from "@/lib/validate-url";

interface FormatPickerProps {
  formats: VideoFormat[];
  advancedFormats: VideoFormat[];
  value: string;
  onChange: (formatId: string, meta?: { advanced: boolean }) => void;
  disabled?: boolean;
}

const ADVANCED_PASSWORD = "0000";

function FormatOption({
  format,
  active,
  disabled,
  name,
  onChange,
}: {
  format: VideoFormat;
  active: boolean;
  disabled?: boolean;
  name: string;
  onChange: () => void;
}) {
  return (
    <label
      className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl border px-4 py-3 transition-colors ${
        active
          ? "rainbow-border border-transparent bg-[var(--surface-2)]"
          : "border-[var(--border)] hover:border-[var(--border-strong)]"
      } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
    >
      <span className="inline-flex items-center gap-3">
        <input
          type="radio"
          name={name}
          value={format.formatId}
          checked={active}
          onChange={onChange}
          className="accent-[var(--accent)]"
        />
        <span>
          <span className="block text-[15px] font-semibold text-[var(--ink)]">
            {format.label}
            <span className="ml-2 font-mono text-xs font-medium uppercase text-[var(--muted)]">
              {format.ext}
            </span>
          </span>
          <span className="mt-0.5 block text-sm text-[var(--muted)]">
            {format.hasVideo ? format.resolution : "僅音訊 · AAC"}
            {format.progressive ? " · 不經伺服器流量" : ""}
          </span>
        </span>
      </span>
      <span className="shrink-0 font-mono text-sm text-[var(--muted)]">
        {formatBytes(format.filesizeApprox)}
      </span>
    </label>
  );
}

export function FormatPicker({
  formats,
  advancedFormats,
  value,
  onChange,
  disabled,
}: FormatPickerProps) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  const advancedIds = useMemo(
    () => new Set(advancedFormats.map((f) => f.formatId)),
    [advancedFormats],
  );

  function tryUnlock(e: React.FormEvent) {
    e.preventDefault();
    if (password === ADVANCED_PASSWORD) {
      setUnlocked(true);
      setPwError(null);
    } else {
      setUnlocked(false);
      setPwError("密碼錯誤，進階選項請輸入 0000 方可使用");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <fieldset disabled={disabled} className="min-w-0">
        <legend className="mb-3 text-sm font-semibold text-[var(--ink-soft)]">
          選擇畫質
        </legend>
        <div className="grid gap-2">
          {formats.map((format) => (
            <FormatOption
              key={format.formatId}
              format={format}
              name="format"
              active={value === format.formatId}
              disabled={disabled}
              onChange={() => onChange(format.formatId, { advanced: false })}
            />
          ))}
        </div>
      </fieldset>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between text-left text-sm font-semibold text-[var(--ink-soft)] disabled:opacity-60"
        >
          <span>進階輸出（MP4 高畫質）</span>
          <span className="font-mono text-xs text-[var(--muted)]">{open ? "▾" : "▸"}</span>
        </button>
        <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
          進階選項請輸入 <span className="font-mono text-[var(--ink)]">0000</span>{" "}
          方可使用（較耗伺服器流量）。
        </p>

        {open && (
          <div className="mt-3 border-t border-[var(--border)] pt-3">
            {!unlocked ? (
              <form onSubmit={tryUnlock} className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1">
                  <label
                    htmlFor="advanced-password"
                    className="mb-1.5 block text-xs font-medium text-[var(--muted)]"
                  >
                    進階密碼
                  </label>
                  <input
                    id="advanced-password"
                    type="password"
                    inputMode="numeric"
                    autoComplete="off"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setPwError(null);
                    }}
                    placeholder="請輸入 0000"
                    disabled={disabled}
                    className="min-h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_var(--ring)]"
                  />
                </div>
                <button
                  type="submit"
                  disabled={disabled || !password}
                  className="btn-ink inline-flex min-h-10 items-center justify-center rounded-lg px-4 text-sm font-semibold disabled:opacity-45"
                >
                  解鎖
                </button>
              </form>
            ) : (
              <p className="mb-3 text-xs text-[var(--muted)]">已解鎖進階 MP4 選項</p>
            )}

            {pwError && (
              <p className="mt-2 text-sm text-[var(--accent)]" role="alert">
                {pwError}
              </p>
            )}

            {unlocked && (
              <fieldset disabled={disabled} className="mt-3">
                {advancedFormats.length === 0 ? (
                  <p className="text-sm text-[var(--muted)]">
                    此影片來源沒有可用的進階 MP4 畫質（720／1080／4K）。
                  </p>
                ) : (
                  <div className="grid gap-2">
                    {advancedFormats.map((format) => (
                      <FormatOption
                        key={`adv-${format.formatId}`}
                        format={format}
                        name="format"
                        active={value === format.formatId}
                        disabled={disabled}
                        onChange={() => onChange(format.formatId, { advanced: true })}
                      />
                    ))}
                  </div>
                )}
              </fieldset>
            )}

            {unlocked && advancedIds.has(value) && (
              <p className="mt-2 text-xs text-[var(--muted)]">
                已選進階 MP4，下載會經伺服器代理合併。
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
