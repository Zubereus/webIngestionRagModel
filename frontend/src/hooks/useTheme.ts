import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark" || value === "system";
}

function prefersDarkTheme(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const storedTheme = localStorage.getItem("webrag_theme");
    return isTheme(storedTheme) ? storedTheme : "system";
  });

  useEffect(() => {
    localStorage.setItem("webrag_theme", theme);
    const root = document.documentElement;
    const applyTheme = () => {
      const useDarkTheme = theme === "dark" || (theme === "system" && prefersDarkTheme());
      root.classList.toggle("dark", useDarkTheme);
    };

    applyTheme();
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", applyTheme);
    return () => mediaQuery.removeEventListener("change", applyTheme);
  }, [theme]);

  return { theme, setTheme };
}
