"use client";

import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={isDark ? "切換為白色風格" : "切換為黑色風格"}
      aria-pressed={isDark}
      title={isDark ? "切換白色風格" : "切換黑色風格"}
    >
      <span className="theme-toggle-knob" aria-hidden>
        {isDark ? "暗" : "亮"}
      </span>
      <span className="sr-only">{isDark ? "目前：黑色風格" : "目前：白色風格"}</span>
    </button>
  );
}
