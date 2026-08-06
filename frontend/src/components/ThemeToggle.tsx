"use client";

import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isLouvre = theme === "louvre";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={isLouvre ? "切換為科技風格" : "切換為羅浮宮風格"}
      aria-pressed={isLouvre}
      title={isLouvre ? "科技風格" : "羅浮宮風格"}
    >
      <span aria-hidden>{isLouvre ? "Louvre" : "Tech"}</span>
      <span className="sr-only">
        {isLouvre ? "目前：羅浮宮風格" : "目前：科技風格"}
      </span>
    </button>
  );
}
