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
      aria-label={isDark ? "切換為淺色美術館" : "切換為深色展廳"}
      aria-pressed={isDark}
      title={isDark ? "淺色美術館" : "深色展廳"}
    >
      <span className="theme-toggle-knob" aria-hidden>
        {isDark ? "夜" : "晝"}
      </span>
      <span className="sr-only">{isDark ? "目前：深色展廳" : "目前：淺色美術館"}</span>
    </button>
  );
}
